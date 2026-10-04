#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch REAL WorkBuddy credit balance + expiry from the billing API and normalise
it into the same shape the cover expects.

Data source (discovered from the usercenter SPA):
  POST https://www.workbuddy.cn/billing/meter/get-user-resource-summary
        -> data.Packages[] : {CycleTotalCapacity, CycleRemainCapacity,
                              CycleUsedCapacity, CapacityUnit, PackageCode}
  POST https://www.workbuddy.cn/billing/meter/get-user-resource
        -> data.Response.Data.Accounts[] : {CycleEndTime, CapacityRemain, ...}

Cookies are required (the same session cookie the browser uses). They are read
from a single source of truth:

  cookies.txt  next to this file   (git-ignored; one raw Cookie-header line,
                                    '#' comment lines are skipped)

To refresh after re-login, just overwrite that one file -- no environment
variable, no relaunch dance beyond restarting the bridge.

The result is cached to credits_cache.json for TTL seconds so we do not hammer
the API on every /cover.png poll. If the live fetch fails we fall back to the
stale cache, then to None (the bridge then uses the static credits.json sample).
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SUMMARY_URL = "https://www.workbuddy.cn/billing/meter/get-user-resource-summary"
DETAIL_URL = "https://www.workbuddy.cn/billing/meter/get-user-resource"
USAGE_URL = "https://www.workbuddy.cn/billing/meter/get-user-request-usage"
CACHE_FILE = os.path.join(HERE, "credits_cache.json")
COOKIE_FILE = os.path.join(HERE, "cookies.txt")
TTL = 180  # seconds between live refreshes (matches the 3-min board refresh)

_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "referer": "https://www.workbuddy.cn/profile/plans-usage",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 "
                   "QuarkPC/7.3.5.1009"),
}


def _cookie():
    """Read the session cookie from cookies.txt next to this file.

    Single source of truth: the file is the ONLY place we look (no env-var
    fallback) so a refresh is just a one-file overwrite. Blank lines and lines
    starting with '#' are ignored, so the file can carry human-readable notes.
    """
    if os.path.isfile(COOKIE_FILE):
        try:
            parts = []
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        parts.append(s)
            return "".join(parts).strip()
        except Exception:
            return ""
    return ""


class _AuthError(Exception):
    """Raised when the API replies 401/403 — i.e. the session cookie is dead."""
    def __init__(self, status, body=""):
        self.status = status
        self.body = body
        super().__init__("auth_http_%d" % status)


def _post_json(url, cookie, body=None):
    payload = json.dumps(body).encode("utf-8") if body is not None else b"{}"
    req = urllib.request.Request(
        url, data=payload, headers=dict(_HEADERS, **{"cookie": cookie}),
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            status = r.status
            return json.loads(r.read().decode("utf-8")), status
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            b = ""
            try:
                b = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            raise _AuthError(e.code, b)
        raise


def _num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def _is_auth_fail(d, status):
    """Some endpoints return HTTP 200 but a non-zero code + a login-required
    message when the cookie is dead. Detect both shapes."""
    if status in (401, 403):
        return True
    if isinstance(d, dict):
        code = d.get("code")
        msg = str(d.get("msg", "") or d.get("message", "") or "")
        if code in (401, 403, 1001, 10001, -1):
            if any(k in msg for k in ("登录", "未登录", "login",
                                      "unauthorized", "token", "过期",
                                      "鉴权", "auth", "请登录")):
                return True
        # 200 with a non-zero code and an explicit login message
        if code not in (0, None) and any(
                k in msg for k in ("登录", "未登录", "login",
                                   "unauthorized", "请登录")):
            return True
    return False


def _parse_summary(data):
    pkgs = (data or {}).get("Packages", []) or []
    rem = used = total = 0.0
    for p in pkgs:
        # 2026-10-04: 所有套餐包（含未动用的"基础包/赠送包"）都计入
        # 剩余/已用/总额——体验版主套餐(007) + 基础包(008/030) 共同构成
        # 可用额度，WorkBuddy 界面也是合并显示的（用户确认基础包要算）。
        rem += _num(p.get("CycleRemainCapacity"))
        used += _num(p.get("CycleUsedCapacity"))
        total += _num(p.get("CycleTotalCapacity"))
    plan = (data or {}).get("SubscriptionPackageName", "") or ""
    return rem, used, total, plan


def _parse_expiry(data, today=None):
    """From the per-account detail, derive a MERGED per-day list of upcoming
    expirations (same-day packages summed, with a package count), plus the
    monthly subscription reset.

    Each account has both a one-time grant expiry (`ExpiredTime`, present only on
    bonus/grant packs) and a monthly cycle end (`CycleEndTime`). We bucket by the
    EFFECTIVE expiry date (ExpiredTime preferred, else CycleEndTime) so the
    subscription's monthly reset shows up as its own merged line and grant packs
    that share a date are summed -- exactly the "查看全部" daily breakdown.

    Only accounts with remaining capacity > 0 and a future expiry date count.
    """
    now = today or datetime.now()
    today_d = now.date()
    accts = (((data or {}).get("Response", {}) or {}).get("Data", {}) or {}).get(
        "Accounts", []) or []
    merged = {}          # date(str) -> [amount, count]
    cycle_end = None
    cycle_remain = 0.0
    for a in accts:
        rem = _num(a.get("CapacityRemain"))
        if rem <= 0:
            continue
        ed = a.get("ExpiredTime") or a.get("CycleEndTime") or ""
        if not ed or len(ed) < 10:
            continue
        try:
            dt = datetime.strptime(ed[:19], "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            continue
        if dt < today_d:
            continue  # already expired -> not "upcoming"
        merged.setdefault(ed[:10], [0.0, 0])
        merged[ed[:10]][0] += rem
        merged[ed[:10]][1] += 1
        # monthly subscription reset: accounts that are pure subscriptions
        # (no one-time ExpiredTime) and whose cycle ends in the current month.
        if not (a.get("ExpiredTime") or ""):
            cend = a.get("CycleEndTime") or ""
            if len(cend) >= 10:
                try:
                    cdt = datetime.strptime(cend[:19], "%Y-%m-%d %H:%M:%S").date()
                except Exception:
                    cdt = None
                if cdt and cdt.year == today_d.year and cdt.month == today_d.month:
                    cycle_remain += _num(a.get("CycleCapacityRemain", rem))
                    if cycle_end is None or cdt > cycle_end:
                        cycle_end = cdt
    out = []
    for dstr, (amt, cnt) in merged.items():
        dt = datetime.strptime(dstr, "%Y-%m-%d").date()
        out.append({
            "amount": round(amt, 2),
            "count": cnt,
            "expireDate": dstr,
            "daysLeft": (dt - today_d).days,
        })
    out.sort(key=lambda e: e["expireDate"])
    cyc = None
    if cycle_end is not None:
        cyc = {
            "expireDate": cycle_end.strftime("%Y-%m-%d"),
            "daysLeft": (cycle_end - today_d).days,
            "amount": round(cycle_remain, 2),
        }
    return out, cyc


def fetch_usage(days=7, max_pages=10):
    """Live per-request credit consumption (the 积分消耗明细 API, v1).
    Aggregates credits per local day. Returns:
      {"daily": {date: credits, ...}, "total": X, "today": X}
    """
    today = datetime.now()
    start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    start = start - timedelta(days=days - 1)
    daily = {}
    total_known = None
    got = 0
    page = 1
    while page <= max_pages:
        body = {
            "startTime": start.strftime("%Y-%m-%d 00:00:00"),
            "endTime": today.strftime("%Y-%m-%d 23:59:59"),
            "pageNum": page,
            "pageSize": 1000,
        }
        d, _s = _post_json(USAGE_URL, cookie=_cookie(), body=body)
        if not d or d.get("code") != 0:
            break
        data = d.get("data") or {}
        rows = data.get("data") or []
        if total_known is None:
            total_known = int(data.get("total") or 0)
        for r in rows:
            day = str(r.get("requestTime", ""))[:10]
            try:
                c = float(r.get("credit") or 0)
            except Exception:
                c = 0.0
            daily[day] = daily.get(day, 0.0) + c
        got += len(rows)
        if got >= (total_known or 0) or not rows:
            break
        page += 1
    if not daily:
        return None
    today_s = today.strftime("%Y-%m-%d")
    daily = {k: round(v, 2) for k, v in sorted(daily.items())}
    return {
        "daily": daily,
        "today": daily.get(today_s, 0.0),
        "total": round(sum(daily.values()), 2),
        "days": days,
    }


# Friendly Chinese labels for WorkBuddy's internal request-step types. These
# are the closest thing the usage API exposes to "what cost credits".
_AGENT_LABELS = {
    "conversation": "对话",
    "conversation:compact": "对话压缩",
    "context_summary_max_token": "上下文压缩",
    "context_summary_pre_message": "上下文预处理",
    "webfetch": "联网检索",
    "conversation_topic": "主题归纳",
    "image_generation": "图像生成",
    "code_execution": "代码执行",
}


def fetch_agent_usage(days=7, max_pages=10):
    """Live per-request credit burn grouped by the request step type
    (agentPurpose). The usage API does not expose the user's *task/space name*,
    only these internal step labels -- but each carries a REAL credit number,
    which is exactly what the board needs to stop showing fake percentages.

    Returns a list of task dicts (highest cost first):
      {"name", "status", "progress", "credits", "date", "detail", "src"}
    status is "running" if the step fired within AGENT_RUN_HOURS, else "done".
    """
    from datetime import timedelta
    AGENT_RUN_HOURS = 6.0
    today = datetime.now()
    start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start - timedelta(days=days - 1)
    agg = {}            # label -> {"credits": float, "last": datetime}
    total_known = None
    got = 0
    page = 1
    while page <= max_pages:
        body = {
            "startTime": start.strftime("%Y-%m-%d 00:00:00"),
            "endTime": today.strftime("%Y-%m-%d 23:59:59"),
            "pageNum": page,
            "pageSize": 1000,
        }
        try:
            d, _s = _post_json(USAGE_URL, cookie=_cookie(), body=body)
        except _AuthError:
            return []   # cookie dead -> no live tasks; caller falls back
        except Exception:
            break
        if not d or d.get("code") != 0:
            break
        data = d.get("data") or {}
        rows = data.get("data") or []
        if total_known is None:
            total_known = int(data.get("total") or 0)
        for r in rows:
            ap = str(r.get("agentPurpose") or "").strip() or "other"
            c = _num(r.get("credit"))
            label = _AGENT_LABELS.get(ap, ap.replace("_", " "))
            g = agg.get(label)
            if g is None:
                g = {"credits": 0.0, "last": None}
                agg[label] = g
            g["credits"] += c
            ts = str(r.get("requestTime") or "")
            try:
                dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = None
            if dt and (g["last"] is None or dt > g["last"]):
                g["last"] = dt
        got += len(rows)
        if got >= (total_known or 0) or not rows:
            break
        page += 1
    if not agg:
        return []
    now = datetime.now()
    max_c = max(g["credits"] for g in agg.values()) or 1.0
    tasks = []
    for label, g in agg.items():
        last = g["last"]
        hours = (now - last).total_seconds() / 3600.0 if last else 1e9
        running = hours <= AGENT_RUN_HOURS
        tasks.append({
            "name": label,
            "status": "running" if running else "done",
            # progress bar = share of the biggest coster (a cost-distribution
            # visual, not a fake completion %)
            "progress": round(g["credits"] / max_c, 3),
            "credits": round(g["credits"], 2),
            "date": last.strftime("%Y-%m-%d %H:%M") if last else "",
            "detail": "近%d日 %.1f 积分" % (days, g["credits"]),
            "src": "live-usage",
        })
    tasks.sort(key=lambda t: t["credits"], reverse=True)
    return tasks


def fetch_once():
    cookie = _cookie()
    if not cookie:
        return {"authExpired": True, "noCookie": True}
    # balance (hard requirement)
    try:
        summary, s1 = _post_json(SUMMARY_URL, cookie)
    except _AuthError:
        return {"authExpired": True}
    except Exception:
        return None  # network / transient -> fall back to cache
    if _is_auth_fail(summary, s1):
        return {"authExpired": True}
    rem, used, total, plan = _parse_summary(summary.get("data", {}))
    # expiry (best-effort, but an auth failure here still means dead cookie)
    expiry, cycle = [], None
    try:
        detail, s2 = _post_json(DETAIL_URL, cookie)
        if _is_auth_fail(detail, s2):
            return {"authExpired": True}
        if detail and detail.get("code") == 0:
            expiry, cycle = _parse_expiry(detail.get("data", {}))
    except _AuthError:
        return {"authExpired": True}
    except Exception:
        pass
    # live burn (best-effort)
    usage = None
    try:
        usage = fetch_usage(days=7)
    except _AuthError:
        return {"authExpired": True}
    except Exception:
        pass
    return {
        "remaining": round(rem, 2),
        "used": round(used, 2),
        "total": round(total, 2),
        "plan": plan,
        "cycle": cycle,        # monthly reset {expireDate, daysLeft, amount}
        "expiring": expiry,    # upcoming buckets, reference only
        "usage": usage,        # live burn {daily, today, total, days}
        "authExpired": False,
        "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_credits(force=False):
    """Return normalised credits dict, using cache when fresh. On a hard
    network failure we return the stale cache (if any); on an auth failure we
    surface a stale balance flagged authExpired=True so the cover can warn
    instead of silently showing fake sample data."""
    now = time.time()
    cached = None
    if os.path.isfile(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except Exception:
            cached = None
    if not force and cached is not None and (now - cached.get("_ts", 0)) < TTL:
        return cached
    try:
        live = fetch_once()
    except Exception:
        live = None
    if live is None:
        return cached  # hard/network failure -> stale if available, else None
    if live.get("authExpired"):
        # never cache the failure; prefer last-known balance, flagged expired
        if cached is not None and (cached.get("remaining") or 0) > 0:
            cached["authExpired"] = True
            cached["live"] = False
            return cached
        live["remaining"] = 0
        live["live"] = False
        live["authExpired"] = True
        return live
    live["_ts"] = now
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(live, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return live


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(get_credits(force=True), ensure_ascii=False, indent=2))
