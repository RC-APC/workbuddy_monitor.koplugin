#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read REAL WorkBuddy task names + per-task credit totals from the desktop
client's own database, so the Kindle board shows exactly what the client shows.

Source of truth (local, no API, no scraping):
  ~/.workbuddy/workbuddy.db
    sessions       -> id, title / custom_title, status, last_activity_at,
                      updated_at, deleted_at, is_background_automation
    session_usage  -> session_id, credit_json  {"<requestId>": credits, ...}

  * The task NAME is `custom_title` if the user renamed it, else `title`
    (which is the client-generated conversation title) -- i.e. byte-identical
    to the sidebar entry in the WorkBuddy client.
  * The per-task TOTAL credits = sum of every value in `credit_json`. That is
    the credits burned by THAT conversation, accumulated across all of its
    requests -- exactly "累计在这个任务上使用的总积分".

Status mapping (client value -> board value):
    working            -> running
    completed / error  -> done
    pending            -> queued

Only the last `days` days are listed, newest activity first.

Window policy (`fetch_sessions`, the default the board uses):
  start with TODAY only. If today has fewer than MIN_TASKS entries, widen the
  window one day at a time (up to MAX_DAYS) until MIN_TASKS are shown. A busy
  day therefore shows just that day, and a quiet one still has something to
  compare against -- without ever dumping a 3-day backlog onto a 1-page
  e-ink screen. meta["windowDays"] reports the window actually used.

The DB is opened READ-ONLY via URI (`mode=ro`) and wrapped in pcall, so if the
client is mid-write or the file is locked we simply return nothing and the
bridge falls back to its other sources instead of crashing.
"""

import datetime
import json
import os
import re
import sqlite3

# Session records store epoch MILLIseconds.
DAYS_DEFAULT = 1          # the board shows TODAY unless it is too quiet
MAX_DAYS = 3              # never widen beyond 3 days
MIN_TASKS = 3             # widen until at least this many rows exist
MAX_TASKS = 12

HOME = os.path.expanduser("~")
DB_CANDIDATES = [
    os.path.join(HOME, ".workbuddy", "workbuddy.db"),
    os.path.join(HOME, "AppData", "Roaming", "WorkBuddy", "workbuddy.db"),
]

# Client status -> board status
_STATUS_MAP = {
    "working": "running",
    "pending": "queued",
    "completed": "done",
    "error": "done",
    "cancelled": "done",
    "canceled": "done",
    "aborted": "done",
}


def _db_path():
    env = os.environ.get("WB_SESSION_DB", "")
    if env and os.path.isfile(env):
        return env
    for p in DB_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _ms(dt_fallback=None):
    return int(dt_fallback or 0)


def _credit_total(credit_json):
    """Sum every credit in the session's credit_json blob.

    Tolerates: NULL/empty, malformed JSON, non-numeric values. Returns None
    when we genuinely do not know (so the board can print '-' instead of a
    misleading 0).
    """
    if not credit_json:
        return None
    if isinstance(credit_json, (int, float)):
        return round(float(credit_json), 2)
    try:
        d = json.loads(credit_json)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    total = 0.0
    n = 0
    for v in d.values():
        try:
            total += float(v)
            n += 1
        except Exception:
            continue
    if n == 0:
        return None
    return round(total, 2)


def _name_of(row):
    """Client-visible task name: a user rename wins over the auto title."""
    for k in ("custom_title", "title"):
        v = (row[k] or "").strip() if k in row.keys() else ""
        if v:
            return v
    return "(未命名任务)"


# Folders whose basename is a throwaway container, not a real "space" the user
# would recognise. Sessions inside them get no prefix -- the raw task name is
# clearer than "2026-10-02-12-11-00 - 修复网络".
_GENERIC_CWD = re.compile(
    r"^(20\d\d-\d\d-\d\d(-\d\d)?(-\d\d)?(-\d\d)?"
    r"|workbuddy|sessions?|projects?|tmp|temp|desktop|downloads?)$",
    re.I,
)


def _space_of(row):
    """The client-side SPACE (workspace) a session belongs to.

    The client's sidebar groups conversations by workspace, and the workspace
    IS the session's cwd -- there is no separate space-name column populated in
    practice (group_title is ~always NULL). So the last path segment is the
    space name, e.g. 'D:/音频插件' -> '音频插件'.

    Auto-generated working dirs (WorkBuddy/2026-10-02-12-11-00, bare
    "sessions", "tmp", ...) are treated as NO space, because a timestamp as a
    prefix is noise, not information.
    """
    cwd = ""
    if "cwd" in row.keys():
        cwd = (row["cwd"] or "").strip()
    if not cwd:
        return ""
    seg = cwd.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].strip()
    if not seg or _GENERIC_CWD.match(seg):
        return ""
    # a bare drive root ("D:") is not a space either
    if re.match(r"^[A-Za-z]:?$", seg):
        return ""
    return seg


def _display_name(row):
    """'空间 - 任务' when the space is meaningful, else just the task name.

    Without the prefix the board is ambiguous: three tasks called
    "修复布局" in three different 空间 are indistinguishable on a 1-page e-ink
    screen. The prefix is omitted only when the space adds nothing.
    """
    name = _name_of(row)
    sp = _space_of(row)
    if not sp or sp in name:
        return name
    return "%s · %s" % (sp, name)


def _is_noise(name):
    """Skip the client's internal scratch sessions -- they are not user tasks
    and their 'names' are meaningless IDs."""
    if not name:
        return True
    if name.startswith("sites-deploy-"):
        return True
    if name.startswith("__"):
        return True
    return False


def fetch_sessions(days=DAYS_DEFAULT, max_tasks=MAX_TASKS, now=None,
                   min_tasks=MIN_TASKS, max_days=MAX_DAYS):
    """-> (tasks, meta). tasks = newest activity first.

    Adaptive window: try `days` (default 1 = today). While the result is
    thinner than `min_tasks` AND the window is still narrower than
    `max_days`, widen by one day and retry, so a quiet day still shows
    context. meta["windowDays"] says how wide it actually had to go.
    """
    db = _db_path()
    if not db:
        return [], {"source": "sessions", "ok": False, "why": "workbuddy.db not found"}
    now = now or datetime.datetime.now()
    days = max(1, int(days))
    max_days = max(days, min(max_days, MAX_DAYS))

    tasks, meta, used = [], None, days
    while True:
        tasks, meta = _query(db, now, days, max_tasks)
        used = days
        if len(tasks) >= min_tasks or days >= max_days:
            break
        days += 1
    meta["days"] = used
    meta["windowDays"] = used
    meta["minTasks"] = min_tasks
    return tasks, meta


def _query(db, now, days, max_tasks):
    """Read one window of sessions from the client's DB."""
    cutoff_ms = int((now - datetime.timedelta(days=max(0, days) - 1)).timestamp() * 1000)
    q = """
        SELECT s.id, s.title, s.custom_title, s.status,
               s.last_activity_at, s.updated_at, s.created_at,
               s.deleted_at, s.is_background_automation, s.cwd,
               u.credit_json
          FROM sessions s
          LEFT JOIN session_usage u ON u.session_id = s.id
         WHERE s.deleted_at IS NULL
           AND COALESCE(s.last_activity_at, s.updated_at, s.created_at) >= ?
         ORDER BY COALESCE(s.last_activity_at, s.updated_at, s.created_at) DESC
    """
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/").replace("?", "%3f"),
                              uri=True, timeout=3)
        con.row_factory = sqlite3.Row
        rows = con.execute(q, (cutoff_ms,)).fetchall()
        con.close()
    except Exception as e:
        return [], {"source": "sessions-db", "ok": False, "why": str(e)}

    out = []
    running = 0
    total_credits = 0.0
    for r in rows:
        name = _name_of(r)
        if _is_noise(name):
            continue
        # background automations are not something the user is "working on"
        if r["is_background_automation"]:
            continue
        ts_ms = _ms(r["last_activity_at"]) or _ms(r["updated_at"]) or _ms(r["created_at"])
        if not ts_ms:
            continue
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0)
        age_h = (now - dt).total_seconds() / 3600.0
        st = _STATUS_MAP.get(str(r["status"] or "").lower(), "done")
        cre = _credit_total(r["credit_json"])
        if cre is not None:
            total_credits += cre
        if st == "running":
            running += 1
        cwd = (r["cwd"] or "").strip()
        out.append({
            # `name` stays the pure client task name (used for de-duplication
            # and by the text board); `display` adds the space prefix so the
            # board can tell same-named tasks in different 空间 apart.
            "name": name,
            "display": _display_name(r),
            "space": _space_of(r),
            "status": st,
            # progress is meaningless for a conversation; the board renders
            # credits instead. Keep 1.0 for done so any legacy percent view
            # still reads as complete.
            "progress": 1.0 if st == "done" else 0.0,
            "credits": cre,
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "ts": ts_ms,
            "detail": "%s · %.0fh前" % (dt.strftime("%m-%d %H:%M"), age_h),
            "cwd": cwd,
            "src": "sessions-db",
        })
        if len(out) >= max_tasks:
            break
    meta = {
        "source": "sessions-db",
        "ok": True,
        "count": len(out),
        "running": running,
        "totalCredits": round(total_credits, 2),
        "db": db,
    }
    return out, meta


if __name__ == "__main__":
    ts, meta = fetch_sessions()
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    for t in ts:
        cre = t["credits"]
        print("  [%-7s] %-42s %s" % (
            t["status"], t["name"][:42],
            ("%9.2f 分" % cre) if cre is not None else "        - 分"))
