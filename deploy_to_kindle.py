"""Copy the plugin onto the Kindle, working around KOReader's file lock.

Why this script exists
----------------------
KOReader keeps a plugin's main.lua / config.txt open while it is running.
On that state:

  * open(dst, "wb")            -> Permission denied [Errno 13]
  * cp -f                      -> "cannot remove ...: Permission denied"
  * os.rename(dst, dst+".old") -> Permission denied

but the *directory* is still writable (you can create new files in it), and
deleting the target works once KOReader lets go.

The reliable recipe is therefore DELETE-FIRST, THEN WRITE FRESH:

    rm -f dst ; cp src dst

Plain overwrite retries forever and never succeeds; rm-then-write succeeds as
soon as the lock is released. (Also note: a plain `cp -f` that reports success
may have only *partially* failed -- always `cmp` afterwards.)

Usage:  python deploy_to_kindle.py            # 20 min retry window
        python deploy_to_kindle.py --once     # single attempt, no retry
"""
import os
import shutil
import sys
import time

SRC = r"D:/kual_deliver/workbuddy-koreader-monitor/workbuddy_monitor.koplugin"
DST = r"F:/koreader/plugins/workbuddy_monitor.koplugin"
FILES = ["main.lua", "config.txt"]


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def deploy_one(name, data):
    """Delete-first write. Returns True when dst now matches `data`."""
    dst = DST + "/" + name
    try:
        if os.path.exists(dst):
            os.remove(dst)                      # <- the trick
        with open(dst, "wb") as f:
            f.write(data)
    except Exception as e:
        print("retry", name, e, flush=True)
        return False
    return _read(dst) == data


def main():
    once = "--once" in sys.argv
    deadline = time.time() + 1800               # 30 min
    while True:
        # Re-read the source every round: the local copy keeps changing while
        # we wait for the Kindle to release its own.
        src_data = {}
        for name in FILES:
            src_data[name] = _read(SRC + "/" + name)
        pending = [n for n in FILES if src_data[n] != _read(DST + "/" + n)]
        if not pending:
            print("DEPLOYED AND VERIFIED: all files identical", flush=True)
            return 0
        for name in pending:
            if deploy_one(name, src_data[name]):
                print("wrote", name, flush=True)
        if once:
            print("single attempt finished; still pending:", pending, flush=True)
            return 1
        if time.time() > deadline:
            print("TIMEOUT: still locked, user action needed", flush=True)
            return 1
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
