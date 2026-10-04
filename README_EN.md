[中文](README.md)

# WorkBuddy KOReader Monitor

Cast your [WorkBuddy](https://workbuddy.cn) agent's **credit balance / task progress** onto a **Kindle / KOReader e-ink screen** as a persistent dashboard. A tiny bridge on the PC (standard-library-only HTTP server) talks to a KOReader plugin on the Kindle over the local network.

> Use case: you have a dusty Kindle and want to glance at "how many credits are left this month, which tasks are running, which are about to expire" on the e-ink screen — no phone, no laptop, just a look.

## Features

- **Persistent dashboard**: stays on the Kindle screen, auto-refreshes every **3 minutes** (re-pulls the PNG from the bridge; the `SYNC <time>` timestamp updates, never freezes).
- **Two themes**: dark (`theme=dark`, white-on-black) / light (`theme=light`, black-on-white), both e-ink-safe grayscale.
- **Three bindable gestures**: `WorkBuddy Dashboard` (toggle) / `WorkBuddy Set Lock-Screen Wallpaper` / `WorkBuddy Exit Dashboard`.
- **Lock-screen cover**: after you tap "Set Lock-Screen Wallpaper", every dashboard refresh copies the latest image into `wb_ss/cover.png`; just point KOReader's screensaver at that folder and the lock screen follows automatically.
- **Offline fallback**: when the bridge can't fetch live data, it falls back to static `credits.json` / `tasks.json` so the screen is never blank.
- **Sleep-proof**: while the dashboard is up, Kindle auto-suspend is paused to avoid "unresponsive / only a reboot fixes it".

## Architecture

```
 WorkBuddy client / account
        │ cookies
        ▼
  ┌─────────────────────┐
  │  PC bridge           │  listens on 0.0.0.0:8765 (stdlib only)
  │  wb-bridge.py        │
  │   · /status.json     │
  │   · /cover.png       │  ← renders status into an 8-bit grayscale PNG via Pillow
  └─────────┬───────────┘
            │  WiFi / LAN
            ▼
  ┌─────────────────────┐
  │  Kindle KOReader     │  workbuddy_monitor.koplugin
  │   · persistent board  │  (refresh every 3 min)
  │   · lock-screen cover │  (wb_ss/)
  └─────────────────────┘
```

## Directory layout

```
workbuddy-koreader-monitor/
├── workbuddy_monitor.koplugin/   # Kindle-side KOReader plugin
│   ├── main.lua                  #   plugin body (board / gestures / lock-screen)
│   └── config.txt                #   1st line = bridge URL, optional theme=dark|light
├── wb-bridge.py                  # PC-side bridge (HTTP server, stdlib only)
├── cover_gen.py                  # PNG rendering (Pillow)
├── fetch_credits.py             # fetch live WorkBuddy credits (needs cookies.txt)
├── wb_sessions.py                # read WorkBuddy local session store
├── parse_usage.py / scan_tasks.py# other data sources
├── deploy_to_kindle.py           # deploy plugin to Kindle (delete-first + verify)
├── bridge_watchdog.bat          # watchdog: relaunch bridge if port not listening
├── _smoke_lua.py                 # plugin smoke test (loads real Lua via lupa)
├── credits.example.json         # static credits template
├── tasks.example.json            # static tasks template
├── README.md                     # Chinese docs
└── README_EN.md                  # English docs
```

## Installation

### 1. PC-side bridge (Windows / macOS / Linux, Python 3.8+, no pip needed)

```bash
cd workbuddy-koreader-monitor
python wb-bridge.py          # listens on 0.0.0.0:8765
```

- Reads `credits.json` / `tasks.json` by default (copy `credits.example.json` / `tasks.example.json` and rename).
- Advanced: drop a `cookies.txt` (the cookie after logging into WorkBuddy in the browser) and the bridge auto-fetches **live credits**; on cookie expiry it falls back to static data.
- Optional auth: env var `WB_TOKEN=xxx` makes the bridge require `Authorization: Bearer xxx`.

### 2. Kindle-side plugin

Connect the Kindle to the PC over USB (on Windows it usually shows up as a drive letter; the script defaults to `F:/`), then:

```bash
python deploy_to_kindle.py          # waits up to 30 min until KOReader releases the file lock, then writes and byte-verifies
python deploy_to_kindle.py --once   # try only once
```

The plugin appears in KOReader's **Plugins** menu. **Restart KOReader once after installing.**

### 3. Configure the bridge URL

Edit line 1 of `workbuddy_monitor.koplugin/config.txt` to your PC's bridge address:

```
http://192.168.137.1:8765     # when the PC is the WiFi hotspot
http://192.168.1.20:8765      # same router: fill in the PC's LAN IP
```

### 4. Bind gestures (optional but recommended)

KOReader: `Settings → Gestures → Add Gesture → draw a gesture → Action list`, then pick:
- **WorkBuddy Dashboard** (tap again to exit — works as a toggle)
- **WorkBuddy Set Lock-Screen Wallpaper**
- **WorkBuddy Exit Dashboard**

### 5. Lock-screen cover (optional)

The plugin menu `Lock-Screen Cover → Show Path & Instructions` shows the absolute path of `wb_ss/cover.png`.
In KOReader: `Settings → Screen → Screensaver type = Random Image`, `Screensaver image folder =` the `wb_ss` folder above.
After you tap "Set Lock-Screen Wallpaper", every dashboard refresh copies the latest image in, and the lock screen updates automatically.

## Auto-start (PC bridge)

- **On login**: `workbuddy_bridge.vbs` in the Startup folder launches `bridge_watchdog.bat` (hidden window, no black box).
- **Fallback**: the Windows scheduled task `WB_Bridge_Watchdog` checks port 8765 every **5 minutes** and relaunches the bridge if it isn't listening; self-heals after a crash / reboot.
- ⚠️ The current setup uses an **InteractiveToken**, i.e. the bridge comes up **after the user logs in** (within ≤5 min), not as a pre-login system service. For "start at boot (before lock screen)" change the scheduled task to a **SYSTEM account + boot trigger**.

## Privacy & credentials

The following files contain credentials / personal data and are **already in `.gitignore` — they never enter the repo**:

`cookies.txt` · `config.js` · `wb_account.json` · `credits_cache.json` · `plans_usage.html`

The bridge listens on the LAN only by default; optional `WB_TOKEN` provides simple Bearer auth.

## FAQ

**Q: Why does the lock screen / dashboard image never update?**
A: First check the PC-side `bridge.log` for `REQ from <Kindle IP>`. None means the WiFi / hotspot link is down (Kindle blocks ICMP, so `ping` failing is normal); if present, the link is fine and the issue is on the render side.

**Q: The timestamp is frozen at an old time?**
A: The persistent board re-pulls the image every 3 minutes, so the timestamp (`SYNC <time>`) changes with it; if it doesn't, the bridge likely isn't receiving requests (see above).

**Q: The Kindle is unresponsive / only a reboot fixes it?**
A: An older build let device sleep swallow touches; that's now fixed by pausing auto-suspend while the board is up.

## License

[MIT](LICENSE) © RC-APC
