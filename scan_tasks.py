#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_tasks.py -- generate REAL "what am I working on" tasks from local file
activity, so the Kindle status board stops showing the fake sample data.

How it works
------------
Auto-discovers working directories on the data drives (top-level folders that
are clearly NOT system/software dirs), walks each one, and finds files edited
within the last RECENT_DAYS. Groups them by the immediate sub-project, then
emits one task per active sub-project with:
  - name     : the sub-project folder name (the real thing you're editing)
  - status   : "running" if touched within HOT_HOURS, else "queued"
  - progress : a RECENCY freshness score in 0..1 (NOT a fake completion %).
               1.0 = edited in the last hour, scaling down to ~0.3 at the edge.
               It tells you how *hot* the project is -- the honest proxy we
               have for "is this still in flight".
  - date     : YYYY-MM-DD of the most recent edit (used by the cover filter)
  - detail   : "<n> files, <x>h ago" -- the raw real signal

This is a genuine activity signal, not a hallucinated percent. If you later wire
up a real task tracker (e.g. a WorkBuddy task API, or push via POST /report),
replace generate_tasks() or merge with _reported in wb-bridge.py.

Usage
-----
  python scan_tasks.py            # prints JSON to stdout
  python scan_tasks.py --write    # also overwrites tasks.json next to this file

wb-bridge.py imports generate_tasks() and calls it on every /status.json
request, so the board always reflects live disk activity.
"""

import os
import sys
import json
import time
import datetime

# ---- configuration -------------------------------------------------------
RECENT_DAYS = 7          # only count files edited within this window
HOT_HOURS = 24           # touched within this -> status "running"
MAX_TASKS = 14           # cap how many we surface on the small e-ink screen
PER_ROOT_FILE_CAP = 8000  # safety cap so a huge tree can't hang the scan

# Top-level system/software folders that must NEVER be treated as a project.
EXCLUDE_TOP = {
    "$RECYCLE.BIN", "System Volume Information", "Config.Msi",
    "Program Files", "ProgramData", "WindowsApps", "WpSystem",
    "Documents", "Temp", "Python", "MySQL", "Quark", "RStudio",
    "SteamLibrary", "WPS Software", "WPS清理大师文件迁移",
    "360", "BaiduNetdiskDownload", "jdk", "pylibs", "eudic",
    "language learning", "extensions", "userbase", "uu", "pr_tmp",
    "c", "apktmp", "cr2xt-0.9.0-18e0eb7-win64-portable",
}

HERE = os.path.dirname(os.path.abspath(__file__))

# Skip these (noise / generated / private) when walking a project tree.
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__", ".workbuddy",
    ".idea", ".vscode", "bin", "obj", "target", "venv", ".venv", "env",
    "Library", "Application Support", "$RECYCLE.BIN", "System Volume Information",
    "out", ".gradle", "Pictures", "Music", "Videos", "Downloads",
}
SKIP_EXT = {
    ".log", ".tmp", ".bak", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".pdf", ".zip", ".gz", ".7z", ".pyc", ".cache", ".DS_Store", ".db",
    ".db-shm", ".db-wal", ".so", ".dll", ".exe",
}


def _load_extra_roots():
    out = []
    p = os.path.join(HERE, "scan_roots.txt")
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln and not ln.startswith("#") and os.path.isdir(ln):
                    out.append(ln)
    return out


def _auto_roots():
    """Auto-discover working directories: every top-level folder on the data
    drives that is not a known system/software folder. This is how the board
    finds 'more than 5 tasks' without the user maintaining a list."""
    roots = []
    for drive in ("D:\\", "E:\\", "F:\\", "G:\\"):
        if not os.path.isdir(drive):
            continue
        try:
            names = os.listdir(drive)
        except OSError:
            continue
        for name in names:
            if name in EXCLUDE_TOP or name.startswith("$"):
                continue
            fp = os.path.join(drive, name)
            try:
                if not os.path.isdir(fp):
                    continue
            except OSError:
                continue
            roots.append(fp)
    return roots


def _iter_roots():
    roots = []
    try:
        roots += _auto_roots()
    except Exception:
        pass
    roots += _load_extra_roots()
    seen, out = set(), []
    for r in roots:
        rp = os.path.normpath(r)
        if rp in seen:
            continue
        if os.path.isdir(rp):
            seen.add(rp)
            out.append(rp)
    return out


def _freshness(age_h):
    """Recency -> 0..1 freshness score."""
    if age_h < 1:
        return 0.95
    if age_h < 6:
        return 0.85
    if age_h < HOT_HOURS:
        return 0.70
    if age_h < HOT_HOURS * 2:
        return 0.50
    return 0.30


def generate_tasks():
    now = time.time()
    cutoff = now - RECENT_DAYS * 86400.0
    groups = {}  # (root, sub) -> {"root","sub","mtimes":[]}

    for root in _iter_roots():
        scanned = 0
        try:
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                # Prune whole subtrees that are older than the window: nothing
                # inside can be recent, so we skip the expensive recursion.
                try:
                    if os.path.getmtime(dirpath) < cutoff:
                        dirs[:] = []
                        continue
                except OSError:
                    pass
                rel = os.path.relpath(dirpath, root)
                # Group by the FIRST path component under the root so nested
                # sub-directories collapse into one project task instead of
                # spawning a duplicate per folder level.
                parts = rel.split(os.sep)
                if rel == "." or not parts[0]:
                    sub = os.path.basename(root)
                else:
                    sub = parts[0]
                for fn in files:
                    if scanned >= PER_ROOT_FILE_CAP:
                        dirs[:] = []
                        break
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in SKIP_EXT:
                        continue
                    fp = os.path.join(dirpath, fn)
                    try:
                        m = os.path.getmtime(fp)
                    except OSError:
                        continue
                    if m < cutoff:
                        continue
                    key = sub
                    g = groups.get(key)
                    if g is None:
                        g = {"sub": sub, "mtimes": []}
                        groups[key] = g
                    g["mtimes"].append(m)
                    scanned += 1
        except Exception:
            continue

    tasks = []
    for key, g in groups.items():
        mtimes = g["mtimes"]
        if not mtimes:
            continue
        newest = max(mtimes)
        age_h = (now - newest) / 3600.0
        d = datetime.datetime.fromtimestamp(newest)
        status = "running" if age_h < HOT_HOURS else "queued"
        tasks.append({
            "name": g["sub"],
            "status": status,
            "progress": _freshness(age_h),
            "date": d.strftime("%Y-%m-%d"),
            "detail": "%d files, %.0fh ago" % (len(mtimes), age_h),
        })

    # hottest first
    tasks.sort(key=lambda t: t["progress"], reverse=True)
    return tasks[:MAX_TASKS]


def main():
    tasks = generate_tasks()
    payload = {
        "updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tasks": tasks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if "--write" in sys.argv:
        out = os.path.join(HERE, "tasks.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
