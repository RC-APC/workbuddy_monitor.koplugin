"""Deploy the WorkBuddy KOReader Monitor plugin onto a Kindle.

WHY THIS EXISTS
---------------
KOReader keeps a plugin's `main.lua` / `config.txt` open while it is running.
On that state:

  * open(dst, "wb")            -> Permission denied [Errno 13]
  * cp -f                      -> "cannot remove ...: Permission denied"
  * os.rename(dst, dst+".old") -> Permission denied

but the *directory* is still writable, and deleting the target works once
KOReader lets go. The reliable recipe is therefore DELETE-FIRST, THEN WRITE
FRESH, then byte-compare to be sure:

    rm -f dst ; cp src dst ; cmp src dst

A plain `cp -f` that reports success may have *partially* failed -- always
verify afterwards (this script does it for you).

USAGE
-----
    # Windows: Kindle mounted as F:, plugin checked out at ./workbuddy_monitor.koplugin
    python deploy_kindle.py --src ./workbuddy_monitor.koplugin \
                            --dst F:/koreader/plugins/workbuddy_monitor.koplugin

    # macOS / Linux: Kindle mounted somewhere under /media or /Volumes
    python deploy_kindle.py --src ./workbuddy_monitor.koplugin \
                            --dst /media/Kindle/koreader/plugins/workbuddy_monitor.koplugin

    # only try once (no wait-for-unlock retry)
    python deploy_kindle.py --src ... --dst ... --once

The destination directory is created automatically if missing. After a
successful deploy, the user must **restart KOReader once** for the plugin to
appear in the "Plugins" menu.

EXIT CODES
----------
    0  all files deployed and verified identical
    1  timeout / still locked / missing source (see stderr)
"""
import argparse
import os
import sys
import time

DEFAULT_TIMEOUT = 1800  # 30 minutes
FILES = ["main.lua", "config.txt", "_meta.lua"]


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def deploy_one(name, src_dir, dst_dir):
    """Delete-first write. Returns True only when dst now matches src bytes."""
    src = os.path.join(src_dir, name)
    dst = os.path.join(dst_dir, name)
    data = _read(src)
    if data is None:
        print("  MISSING SOURCE: %s" % src, file=sys.stderr, flush=True)
        return False
    try:
        if os.path.exists(dst):
            os.remove(dst)  # <- the trick: KOReader releases the lock on delete
        with open(dst, "wb") as f:
            f.write(data)
    except Exception as e:
        print("  retry %s: %s" % (name, e), file=sys.stderr, flush=True)
        return False
    return _read(dst) == data


def main():
    ap = argparse.ArgumentParser(description="Deploy WorkBuddy KOReader Monitor plugin to a Kindle.")
    ap.add_argument("--src", required=True, help="local workbuddy_monitor.koplugin directory")
    ap.add_argument("--dst", required=True, help="Kindle plugins path, e.g. F:/koreader/plugins/workbuddy_monitor.koplugin")
    ap.add_argument("--once", action="store_true", help="single attempt, no retry")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="max seconds to wait for unlock (default 1800)")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print("SOURCE NOT A DIRECTORY: %s" % args.src, file=sys.stderr)
        return 1

    os.makedirs(args.dst, exist_ok=True)

    deadline = time.time() + args.timeout
    while True:
        pending = []
        for name in FILES:
            src_data = _read(os.path.join(args.src, name))
            dst_data = _read(os.path.join(args.dst, name))
            if src_data is None:
                # optional file (e.g. _meta.lua) missing in source -> skip
                continue
            if src_data != dst_data:
                pending.append(name)

        if not pending:
            print("DEPLOYED AND VERIFIED: all files identical", flush=True)
            return 0

        for name in pending:
            ok = deploy_one(name, args.src, args.dst)
            print(("wrote " if ok else "locked/retry ") + name, flush=True)

        if args.once:
            print("single attempt finished; still pending: %s" % pending, file=sys.stderr)
            return 1
        if time.time() > deadline:
            print("TIMEOUT: Kindle still holds the files. Make sure KOReader is "
                  "running and retry, or restart KOReader and run again.", file=sys.stderr)
            return 1
        time.sleep(10)


if __name__ == "__main__":
    sys.exit(main())
