#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy -> KOReader LAN bridge.

A tiny stdlib-only HTTP server that aggregates the agent status into a fixed,
agent-agnostic JSON and (optionally) a cyberpunk cover PNG, so a KOReader
plugin on the Kindle can poll it every 3 minutes.

Routes
  GET  /status.json   -> agent-agnostic status (credits + tasks)
  GET  /cover.png     -> cyberpunk HUD cover rendered from the status
  POST /report        -> let a WorkBuddy automation push a task status
  GET  /health        -> {"ok": true}

Data sources (all editable, no API required):
  credits.json  {"remaining": N, "expiring": [{"amount": N, "daysLeft": D}]}
  tasks.json    [{"name": "...", "status": "running|done|...", "progress": 0..1,
                  "date": "YYYY-MM-DD"}]   # date enables the 3-day recency filter

Run:  python wb-bridge.py        (listens on 0.0.0.0:8765)
Env:  WB_PORT / WB_TOKEN (optional simple bearer token)
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("WB_PORT", "8765"))
TOKEN = os.environ.get("WB_TOKEN", "")
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

# in-memory tasks pushed via POST /report (merged with tasks.json)
_reported = {}


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
    if live and (live.get("remaining") or 0) > 0:
        credits = {
            "remaining": live.get("remaining", 0),
            "used": live.get("used", 0),
            "total": live.get("total", 0),
            "plan": live.get("plan", ""),
            "cycle": live.get("cycle"),
            "expiring": live.get("expiring", []),
            "usage": live.get("usage"),
            "live": True,
        }
    else:
        credits = _load("credits.json", {"remaining": 0, "expiring": []})
        credits["live"] = False
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
    # Tasks pushed manually via POST /report always win and are never dropped.
    for name, t in _reported.items():
        if name not in seen:
            merged.append(t)
            seen.add(name)
    # running first (by recency), done at the end
    merged.sort(key=lambda t: 0 if str(t.get("status", "")).lower() == "running" else 1)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "source": "workbuddy",
        "updatedAt": now,
        "credits": credits,
        "tasks": merged,
        "taskMeta": session_meta,
    }


def _deny(handler):
    handler._send(401, {"error": "unauthorized"})
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

    def _auth(self):
        if not TOKEN:
            return True
        ah = self.headers.get("Authorization", "")
        return ah == ("Bearer " + TOKEN)

    def do_GET(self):
        u = urlparse(self.path)
        _log("REQ from %s  %s" % (self.client_address[0], self.path))
        if u.path in ("/status.json", "/status"):
            if not self._auth():
                return _deny(self)
            self._send(200, build_status())
        elif u.path == "/cover.png":
            if not self._auth():
                return _deny(self)
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

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/report":
            if not self._auth():
                return _deny(self)
            try:
                ln = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(ln) if ln else b"{}"
                payload = json.loads(raw or b"{}")
            except Exception as e:
                self._send(400, {"error": str(e)})
                return
            t = payload.get("task")
            if isinstance(t, dict) and "name" in t:
                _reported[t["name"]] = {
                    "name": t["name"],
                    "status": t.get("status", "unknown"),
                    "progress": t.get("progress", 0),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            self._send(200, {"ok": True, "tasks": len(_reported)})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("WorkBuddy bridge listening on http://0.0.0.0:%d" % PORT)
    print("  status : http://<this-pc-ip>:%d/status.json" % PORT)
    print("  cover  : http://<this-pc-ip>:%d/cover.png?w=1080&h=1440" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
