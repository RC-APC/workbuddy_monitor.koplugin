---
name: install-workbuddy-kindle-monitor
description: "Guide a user to install, deploy, or troubleshoot the WorkBuddy KOReader Monitor plugin on a Kindle or any KOReader e-reader, turning the e-ink screen into a live dashboard of their AI agent status (credits, expiring points, running tasks). Trigger on requests to install the WorkBuddy Kindle plugin, set up the e-ink dashboard, deploy the KOReader monitor, connect a Kindle to show WorkBuddy status, or fix a blank, locked, or login-expired Kindle screen. Also covers LAN versus remote-snapshot configuration and cookie refresh."
agent_created: true
---

# Install WorkBuddy KOReader Monitor

## Overview

This skill codifies the two-part deployment of the **WorkBuddy KOReader Monitor**
plugin so WorkBuddy can walk a user through it without rediscovering the
non-obvious pitfalls each time. The plugin pulls the PC-side WorkBuddy status
(credits, expiring points, running tasks) as a rendered cover image every 3
minutes and shows it on a Kindle e-ink screen.

The install is **two independent halves that each get set up once**:

1. **PC-side bridge** (`wb-bridge.py`) — renders the cover, listens on
   `0.0.0.0:8765`.
2. **Kindle-side plugin** (`workbuddy_monitor.koplugin/`) — fetches the image and
   fills the e-ink screen.

They talk over `http://<PC-IP>:8765`. LAN mode needs same-WiFi; remote mode
(cross-network, the long-term recommendation) pushes snapshots to a private
GitHub raw URL the Kindle fetches instead.

## When to use

Trigger on phrasing like: install the WorkBuddy Kindle plugin, set up the
e-ink dashboard, deploy the KOReader monitor, show WorkBuddy status on my
Kindle, or any troubleshooting of a blank/locked/expired Kindle screen for this
plugin. Do **not** use for general KOReader usage or unrelated plugin installs.

## How to assist (workflow)

1. **Read the full procedure first.** Load `references/install-guide.md` for the
   exact commands, platform differences (Windows drive letter vs. macOS/Linux
   mount point), and the complete troubleshooting section. Keep it as the source
   of truth; do not paraphrase the steps from memory.
2. **Confirm the environment before acting:** which OS is the PC, is the Kindle
   USB-mounted (and its mount path), is KOReader currently running on the Kindle,
   and is the user doing LAN or remote mode.
3. **PC bridge first.** Have the user `pip install pillow` and run `wb-bridge.py`
   (or double-click `workbuddy_bridge.vbs` on Windows). Verify with
   `http://127.0.0.1:8765/cover.png`.
4. **Kindle plugin via the bundled deploy script.** Run
   `scripts/deploy_kindle.py --src ./workbuddy_monitor.koplugin --dst <kindle>/koreader/plugins/workbuddy_monitor.koplugin`.
   The script waits out KOReader's file lock, writes, and byte-verifies. Tell the
   user to **restart KOReader once** afterward.
5. **Configure the bridge address.** Edit the plugin `config.txt` line 1, or set
   it from the KOReader plugin menu, to `http://<PC-LAN-IP>:8765` (LAN) or the
   GitHub raw URL (remote). Verify the e-ink screen shows the credit ring.

## Critical gotchas (never skip)

These are the reasons a naive install fails — surface them proactively:

- **KOReader file lock (坑 1).** While KOReader runs it locks `main.lua` /
  `config.txt`; `cp -f` reports success but may write only partially. Always
  **delete-first then write**, which `scripts/deploy_kindle.py` does. If it
  hits `TIMEOUT`, confirm KOReader is running or restart it.
- **DHCP IP drift (坑 2).** The PC LAN IP changes on reconnect/sleep/router
  reboot. A mismatch = blank screen. Re-check with `ipconfig` / `ifconfig` and
  redeploy.
- **Cookie expiry (坑 3).** `cookies.txt` is a session credential that expires.
  On expiry the bridge clearly alarms (Kindle top banner `▲ 登录已失效`,
  `CREDITS` badge `LIVE` → `EXPIRED`). Recovery: re-login workbuddy.cn → F12
  copy the new `cookie:` value → replace line 1 of `cookies.txt` → restart the
  bridge.
- **Must restart KOReader (坑 4).** Copying the plugin without restarting
  KOReader hides it from the Plugins menu.
- **Multiple bridges (坑 5).** `SO_REUSEADDR` lets several bridges bind 8765;
  double-clicking the vbs stacks them and corrupts the cover. `netstat` should
  show exactly one LISTEN on 8765.

## Resources

- `references/install-guide.md` — complete, copy-pasteable procedure: prerequisites,
  PC bridge, Kindle USB deploy, bridge-address config, remote-snapshot mode,
  gestures/lockscreen extras, and the full troubleshooting list with the exact
  cookie-refresh steps.
- `scripts/deploy_kindle.py` — parametrized, cross-platform deployer that handles
  the KOReader file lock (delete-first + byte-verify) and waits for unlock. Run
  with `--src` and `--dst`; add `--once` to skip the retry loop.
