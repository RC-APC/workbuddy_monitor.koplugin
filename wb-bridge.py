#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy -> KOReader LAN bridge.

A tiny stdlib-only HTTP server that aggregates the agent status into a fixed,
agent-agnostic JSON and (optionally) a cyberpunk cover PNG, so a KOReader
plugin on the Kindle can poll it every 3 minutes.

Routes
  GET  /status.json   -> agent-agnostic status (credits + tasks)
  GET  /cover.png     -> cyberpunk HUD cover rendered from the status
  GET  /health        -> {"ok": true}

Data sources (all editable, no API required):
  credits.json  {"remaining": N, "expiring": [{"amount": N, "daysLeft": D}]}
  tasks.json    [{"name": "...", "status": "running|done|...", "progress": 0..1,
                  "date": "YYYY-MM-DD"}]   # date enables the 3-day recency filter

Run:  python wb-bridge.py        (listens on 0.0.0.0:8765)
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# pythonw (silent launcher) has no console: sys.stdout/stderr are None and
# ANY print() raises AttributeError, killing the process right after bind.
# Redirect both to a log file so prints are harmless and diagnosable.
if sys.stdout is None or sys.stderr is None:
    _crashlog = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "bridge_stdout.log"),
                     "w", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _crashlog
    if sys.stderr is None:
        sys.stderr = _crashlog

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("WB_PORT", "8765"))
LOGPATH = os.path.join(DATA_DIR, "bridge.log")


def _log(msg):
    """Append one line to bridge.log.

    Exists purely so we can tell apart the two failure modes that look
    identical on the device: (a) the Kindle never reached us at all (WiFi /
    hotspot trouble) versus (b) it did fetch a fresh PNG but kept painting an
    old one (device-side caching / refresh).
    """
    try:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass





def _load(name, default):
    p = os.path.join(DATA_DIR, name)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("warn: cannot read %s: %s" % (name, e))
    return default


def build_status():
    # Live credit balance + monthly reset from the WorkBuddy billing API.
    # Falls back to the static credits.json sample when the API is unreachable
    # (e.g. cookies expired) so the cover always has something to draw.
    try:
        import fetch_credits
        live = fetch_credits.get_credits()
    except Exception as e:
        print("warn: fetch_credits failed: %s" % e)
        live = None
    auth_expired = bool(live.get("authExpired")) if live else False
    no_cookie = bool(live.get("noCookie")) if live else False
    if live and (live.get("remaining") or 0) > 0:
        credits = {
            "remaining": live.get("remaining", 0),
            "used": live.get("used", 0),
            "total": live.get("total", 0),
            "plan": live.get("plan", ""),
            "cycle": live.get("cycle"),
            "expiring": live.get("expiring", []),
            "usage": live.get("usage"),
            # keep the last-known balance visible, but flag it stale so the
            # cover can shout "EXPIRED" instead of silently showing frozen LIVE
            "live": not auth_expired,
        }
    else:
        credits = _load("credits.json", {"remaining": 0, "expiring": []})
        credits["live"] = False
    # surface auth failures to the cover so a dead cookie is NEVER silent
    credits["authExpired"] = auth_expired
    credits["noCookie"] = no_cookie
    # 0) BEST SOURCE: the WorkBuddy client's OWN database
    #    (~/.workbuddy/workbuddy.db). It carries the exact task name shown in
    #    the client sidebar plus the credits that conversation has burned in
    #    total (session_usage.credit_json). No guessing, no exports, no API.
    try:
        import wb_sessions
        session_tasks, session_meta = wb_sessions.fetch_sessions()
    except Exception as e:
        print("warn: wb_sessions failed: %s" % e)
        session_tasks, session_meta = [], {"ok": False, "why": str(e)}
    # 1) Real per-task credits from a manual usage-page export (积分消耗明细 ->
    #    导出). Best source: carries the user's actual task/space title + real
    #    credits.
    try:
        import parse_usage
        usage_tasks = parse_usage.aggregate()
    except Exception as e:
        print("warn: parse_usage failed: %s" % e)
        usage_tasks = []
    # 2) Live credit burn grouped by request step type (agentPurpose) from the
    #    usage API. Always available when the cookie is valid, and each row
    #    carries a REAL credit number -- so the board shows credits, not a fake
    #    percentage.
    try:
        import fetch_credits
        agent_tasks = fetch_credits.fetch_agent_usage(days=7) or []
    except Exception as e:
        print("warn: fetch_agent_usage failed: %s" % e)
        agent_tasks = []
    # 3) Local file activity (folder names, only a freshness %). Fallback only.
    try:
        from scan_tasks import generate_tasks
        scanned = generate_tasks() or []
    except Exception as e:
        print("warn: scan_tasks failed: %s" % e)
        scanned = []
    # Priority: the client's own session DB (real names + real per-task totals)
    #   > CSV export > live agent breakdown > local folder scan.
    if session_tasks:
        chosen = session_tasks
    elif usage_tasks:
        chosen = usage_tasks
    elif agent_tasks:
        chosen = agent_tasks
    else:
        chosen = scanned
    # Only fall back to the static sample/draft tasks.json when nothing live.
    file_tasks = _load("tasks.json", []) if not chosen else []
    seen = set()
    merged = []
    for t in chosen + file_tasks:
        if isinstance(t, dict) and "name" in t and t["name"] not in seen:
            merged.append(t)
            seen.add(t["name"])
    # running first (by recency), done at the end
    merged.sort(key=lambda t: 0 if str(t.get("status", "")).lower() == "running" else 1)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "source": "workbuddy",
        "updatedAt": now,
        "credits": credits,
        "tasks": merged,
        "taskMeta": session_meta,
        # surfaced so a missing-Pillow runtime (e.g. a bare managed
        # pythonw that lacks the module) is visible instead of producing
        # silent cover-render failures. The double-click vbs reads this too.
        "pillow": _have_pillow(),
    }


def _have_pillow():
    try:
        import importlib.util as _u
        return _u.find_spec("PIL") is not None
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        _log("REQ from %s  %s" % (self.client_address[0], self.path))
        if u.path in ("/status.json", "/status"):
            self._send(200, build_status())
        elif u.path == "/cover.png":
            try:
                from cover_gen import render_cover
                qs = parse_qs(u.query)
                w = int(qs.get("w", ["1080"])[0])
                h = int(qs.get("h", ["1440"])[0])
                w = max(200, min(w, 3000))
                h = max(200, min(h, 4000))
                mono = qs.get("mono", ["1"])[0] != "0"  # Kindle=e-ink, default mono
                layout = qs.get("layout", ["grouped"])[0]
                rday = int(qs.get("rday", ["3"])[0])
                maxn = int(qs.get("maxn", ["10"])[0])
                # the exit hint is DRAWN INTO the png: a KOReader widget overlay
                # (TopContainer with dimen=screen) pushed the cover off-screen.
                # Screensaver use turns it off with ?exit=0.
                ehint = qs.get("exit", ["1"])[0] != "0"
                # theme=dark -> black bg/white text; theme=light -> white
                # bg/black text. Both grayscale, both e-ink safe.
                theme = qs.get("theme", ["dark"])[0]
                if theme not in ("dark", "light"):
                    theme = "dark"
                t0 = time.time()
                png = render_cover(build_status(), w=w, h=h, mono=mono,
                                   task_layout=layout, max_recent_days=rday,
                                   max_count=maxn, exit_hint=ehint,
                                   theme=theme)
                _log("COVER ok %d bytes in %.2fs (w=%d h=%d theme=%s)"
                     % (len(png), time.time() - t0, w, h, theme))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(png)
            except Exception as e:
                _log("COVER FAIL %s" % e)
                self._send(500, {"error": str(e)})
        elif u.path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
        print("WorkBuddy bridge listening on http://0.0.0.0:%d" % PORT)
        print("  status : http://<this-pc-ip>:%d/status.json" % PORT)
        print("  cover  : http://<this-pc-ip>:%d/cover.png?w=1080&h=1440" % PORT)
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    except Exception:
        # any startup/serve failure (port busy, import error, ...) must leave
        # a readable traceback in bridge_stdout.log instead of dying silently
        import traceback
        print("!! bridge crashed:", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        raise SystemExit(1)
