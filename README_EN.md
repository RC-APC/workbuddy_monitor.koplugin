[中文](README.md)

# WorkBuddy KOReader Monitor

Cast your [WorkBuddy](https://workbuddy.cn) agent's **credit balance / task progress** onto a **Kindle / KOReader e-ink screen** as a persistent dashboard. A tiny bridge on the PC (standard-library + Pillow HTTP server) talks to a KOReader plugin on the Kindle — over the same WiFi (LAN direct), or cross-network via a GitHub snapshot for remote viewing (the Kindle can read it from anywhere).

> Use case: you have a dusty Kindle and want to glance at "how many credits are left this month, which tasks are running, which are about to expire" on the e-ink screen — no phone, no laptop, just a look.

## Features

- **Persistent dashboard**: stays on the Kindle screen, auto-refreshes every **3 minutes** (re-pulls the PNG from the bridge; the `SYNC <time>` timestamp updates, never freezes).
- **Two themes**: dark (`theme=dark`, white-on-black) / light (`theme=light`, black-on-white), both e-ink-safe grayscale.
- **Three bindable gestures**: `WorkBuddy Dashboard` (toggle) / `WorkBuddy Set Lock-Screen Wallpaper` / `WorkBuddy Exit Dashboard`.
- **Works on keypad-only Kindles too**: on button-only devices like the Kindle 3 (no touchscreen), just press **any physical key** (page-turn buttons / 5-way directional / Back) to dismiss the board — no gesture needed.
- **Lock-screen cover**: after you tap "Set Lock-Screen Wallpaper", every dashboard refresh copies the latest image into `wb_ss/cover.png`; just point KOReader's screensaver at that folder and the lock screen follows automatically.
- **Offline fallback**: when the bridge can't fetch live data, it falls back to static `credits.json` / `tasks.json` so the screen is never blank.
- **Sleep-proof**: while the dashboard is up, Kindle auto-suspend is paused to avoid "unresponsive / only a reboot fixes it".
- **Login-expiry alert**: when the cookie expires, the cover shows a full-width inverted alert bar `▲ login expired, refresh cookies.txt`, the `CREDITS` badge flips to an inverted `EXPIRED`, and the balance freezes at its last known value marked as expired; the PC launcher also pops a warning on launch.
- **Space-prefixed task names**: active tasks that belong to a workspace show as `space-task` on the cover (tasks without a workspace show their bare name).
- **Today's usage**: the Kindle text board additionally shows `TODAY USED: X credits`, aligned with the WorkBuddy web UI.

## Architecture

```
 WorkBuddy web (workbuddy.cn)
        │ cookies.txt (browser cookie after login)
        ▼
  ┌─────────────────────┐
  │  PC bridge           │  listens on 0.0.0.0:8765 (stdlib + Pillow)
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
│   ├── config.txt                #   1st line = bridge URL, optional theme=dark|light
│   └── _meta.lua                 #   plugin metadata
├── wb-bridge.py                  # PC-side bridge (HTTP server, stdlib + Pillow)
├── cover_gen.py                  # PNG rendering (Pillow)
├── fetch_credits.py              # fetch live WorkBuddy credits (needs cookies.txt)
├── wb_sessions.py                # read WorkBuddy local session store (tasks)
├── parse_usage.py / scan_tasks.py# other data sources
├── deploy_to_kindle.py           # deploy plugin to Kindle (delete-first + verify)
├── workbuddy_bridge.vbs          # Windows launcher (double-click; health check + expiry popup)
├── publish_snapshot.py           # remote snapshot push (view from outside the LAN, see "Remote viewing")
├── publish.ini.example           # remote snapshot config template (copy to publish.ini)
├── cookies.txt.example           # cookies.txt template + how to grab the cookie
├── credits.example.json          # static credits template
├── tasks.example.json            # static tasks template
├── assets/                       # example cover images (dark / light)
└── README.md / README_EN.md      # Chinese / English docs
```

> ⚠️ The old launchers `run_bridge.bat` / `bridge_watchdog.bat` / `_smoke_lua.py` are no longer shipped; use `workbuddy_bridge.vbs`.

## Installation

### 1. PC-side bridge (Windows / macOS / Linux, Python 3.8+, needs Pillow)

```bash
cd workbuddy-koreader-monitor
pip install pillow          # the only third-party dependency
python wb-bridge.py         # listens on 0.0.0.0:8765
```

**Easiest (Windows)**: just double-click `workbuddy_bridge.vbs` — it auto-locates Python (PATH → `pyw` launcher → WorkBuddy-managed Python), frees port 8765 if held, launches the bridge silently, and runs a health check via `ServerXMLHTTP` (which bypasses the system proxy hijacking `127.0.0.1`), then shows a confirmation box.

- Reads `credits.json` / `tasks.json` by default (copy `credits.example.json` / `tasks.example.json` and rename).
- **Live credits**: drop a `cookies.txt` (the cookie after logging into WorkBuddy in the browser) and the bridge auto-fetches **live credits** and **today's usage**; on cookie expiry it falls back to static data and alerts on the cover. See `cookies.txt.example`.

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

> The IP on the same WiFi is DHCP-assigned and may change after reconnect / wake-from-sleep / router reboot; re-check with `ipconfig` and redeploy when it does. An address set in the KOReader plugin menu overrides `config.txt`.

### 4. Bind gestures (optional but recommended)

KOReader: `Settings → Gestures → Add Gesture → draw a gesture → Action list`, then pick:
- **WorkBuddy Dashboard** (tap again to exit — works as a toggle)
- **WorkBuddy Set Lock-Screen Wallpaper**
- **WorkBuddy Exit Dashboard**

### 5. Lock-screen cover (optional)

The plugin menu `Lock-Screen Cover → Show Path & Instructions` shows the absolute path of `wb_ss/cover.png`.
In KOReader: `Settings → Screen → Screensaver type = Random Image`, `Screensaver image folder =` the `wb_ss` folder above.
After you tap "Set Lock-Screen Wallpaper", every dashboard refresh copies the latest image in, and the lock screen updates automatically.

## What if the login expires (important)

The cookie is a session credential and expires (days to weeks). When it does, the bridge **no longer silently pretends to be fine** — it alerts clearly:

- **Kindle cover**: a full-width inverted alert bar `▲ login expired, refresh cookies.txt`; the `CREDITS` badge flips from `LIVE` to an inverted `EXPIRED`; the balance keeps its last known value but is clearly marked expired.
- **PC side**: double-clicking `workbuddy_bridge.vbs` shows a yellow warning if it detects expiry, telling you to update `cookies.txt`.

Recovery (about 1 minute):
1. Re-log into `workbuddy.cn` in the browser (log out then in, or wait for session renewal).
2. **Grab the new cookie**: F12 → Network → refresh → click any request to `workbuddy.cn` → Headers → Request Headers → find the `cookie:` line → **right-click → Copy value** (copy the whole string).
3. Open `cookies.txt` and **replace line 1 entirely** with the new string, save (lines starting with `#` are ignored).
4. **Double-click `workbuddy_bridge.vbs`** to restart the bridge. When the alert bar disappears, the badge returns to `LIVE`, and the balance starts moving again, you're back (Kindle refreshes every 3 minutes).

> Don't grab the cookie from "Copy as cURL" — it works but is messier than method 2 above. The bridge reads **only `cookies.txt`**, not the `WB_COOKIE` env var.

## Auto-start (PC bridge)

- **After login**: put a shortcut to `workbuddy_bridge.vbs` in the Startup folder (`shell:startup`) to launch silently on login.
- **Crash self-heal**: a Windows scheduled task triggered "At log on" calling the vbs; or poll port 8765 every 5 min (`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen"`) and restart if not listening.
- ⚠️ These use an **InteractiveToken**, i.e. the bridge comes up **after the user logs in** (within ~1 min), not as a pre-login system service. For "start at boot (before lock screen)" change the scheduled task to a **SYSTEM account + boot trigger**.

## Privacy & credentials

The following files contain credentials / personal data and are **already in `.gitignore` — they never enter the repo**:

`cookies.txt` · `credits_cache.json` · `config.js` · `index.js` · `plans_usage.html` · `wb_account.json` · `bridge*.log` · `publish.ini`

The bridge listens on the LAN only by default. The cookie is used only to pull your own WorkBuddy data locally and is not uploaded to any third party.

## Remote mode (cross-network, recommended)

**Remote mode** is for "the Kindle and PC are not on the same WiFi, or you want to peek at the board while away": the PC periodically pushes the rendered cover to the cloud and the Kindle reads a fixed https URL — the two sides never need to be on the same network. Compared with LAN direct, it needs no public IP, no port forwarding, no tunnel, and the board keeps showing the last snapshot after the PC goes offline.

```
PC bridge (local, outbound only)  --push-->  GitHub repo  --raw-->  Kindle on any network
```

| | LAN direct | Remote snapshot |
|---|---|---|
| Bridge URL | `http://192.168.x.x:8765` | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>` (**use a mirror in mainland China, see below, or the screen reports "network unreachable"**) |
| Freshness | live (3-min refresh) | last push (every 10 min by default) |
| PC needs | same network as Kindle | internet access only — no public IP, no port forwarding, no tunnel |
| PC off | board shows an error | keeps showing the last snapshot |

**One-time setup (~3 min)**

1. Create an empty GitHub repo; pick a random name (e.g. `wb-board-xxxxxx`). Public is fine — private repos on the free plan cannot be raw-linked anonymously.
2. Create a fine-grained token: Repository access = that one repo, permission `Contents: Read and write`.
3. Copy `publish.ini.example` to `publish.ini` and fill in `owner` / `repo` / `token`.
4. Verify and get the URL:
```bash
python publish_snapshot.py --check            # verify repo + token, print the URL for the Kindle
python publish_snapshot.py --once --dry-run   # fetch a cover without uploading
python publish_snapshot.py --once             # push once for real
python publish_snapshot.py --loop             # keep pushing (every 600s / 10 min by default)
```
5. On the Kindle, 设置桥地址 = one of the URLs below (the plugin auto-appends `/cover_dark.png` or `/cover_light.png` by theme, and `/status.json` — **do not add the filename yourself**):

   - **Outside mainland China / can reach GitHub directly**: `https://raw.githubusercontent.com/<owner>/<repo>/<branch>`
   - **Mainland China (recommended — `raw.githubusercontent.com` is often blocked / times out there, so the screen would report "network unreachable")**: use a mirror that is directly reachable:

     | Mirror | Bridge URL for the Kindle |
     |---|---|
     | **ghproxy.net** (recommended, verified stable) | `https://ghproxy.net/https://raw.githubusercontent.com/<owner>/<repo>/<branch>` |
     | **jsDelivr** (fallback, CDN can time out) | `https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>` |

     > ⚠️ Mirror URL format: jsDelivr uses `@branch` (not `/branch`). jsDelivr's CDN can time out intermittently (verified: connection failures that make the plugin fall back to the text board), so **ghproxy.net is the more reliable choice**; mirrors cache files for **a few minutes**, so remote refresh lags slightly beyond the 10-min interval — normal.
     >
     > Example: if your relay repo is `wb-board-xxxxxx` on branch `main`, the ghproxy URL is `https://ghproxy.net/https://raw.githubusercontent.com/<owner>/wb-board-xxxxxx/main`.

**The repo does not bloat (handled automatically)**

`history = single` in `publish.ini` (the default) pushes through the Git Database API: each push builds a tree with just those two files, creates a **parentless commit**, and force-moves the branch to it. Result:

- History stays at **exactly 1 commit**; old objects become unreachable and GitHub GCs them → constant repo size, **no manual cleanup ever**.
- Identical content produces no commit at all.
- The public raw URL **never changes**, so the Kindle setup is unaffected.

Switch to `history = append` only if you actually want the history (then expect ~144 commits/day at the default 600s interval, needing periodic manual cleanup).

**Notes**

- Remote mode uses `https`, which needs `ssl.https` (lua-sec) in KOReader. Almost every build ships it; if not, the error board shows `https 支持: 不可用 (缺 ssl.https 模块)`.
- The default `interval` is 600s (10 min); no need to go lower. Under `history = single` the interval only affects API usage, not repo size.
- `publish_snapshot.vbs` starts the pusher silently in the background (double-click = `--loop`); output goes to `publish.log` (the script writes it itself, because `pythonw` has no console).
- You see a **snapshot**, not a live frame; the last push survives the PC going offline.
- `publish.ini`'s `width` / `height` = **the cover size pushed to GitHub** (remote mode is one fixed-size image that can't serve multiple device sizes at once). **Set them to the screen resolution of the device you mainly view the board on** — otherwise that device only shows the *center crop* of the larger image, not the whole board. Common values are in "What width/height to set per device" below.

### What width/height to set per device

Remote mode pushes one **fixed-size** image, and the plugin displays it 1:1 (it does not auto-scale to fit). So the image dimensions must match the screen of the device you view it on, or it won't fill the screen correctly.

| Device | width | height |
|---|---|---|
| Kindle 3 / Keyboard / Kindle 4 / Touch (600×800 screen) | 600 | 800 |
| Kindle Paperwhite 1 / 2 (758×1024 screen) | 758 | 1024 |
| Kindle Paperwhite 3 / 4 / 5, Voyage, Oasis (hi-res) | 1072 | 1448 |

- **Not sure of your resolution?** Trigger the board once from the plugin menu; the error / info page prints `screen: WxH`, which is your actual device resolution.
- **One device**: set `width` / `height` to its resolution and the remote snapshot fills perfectly.
- **Multiple devices**: one image serves one resolution — whatever you put in `ini`, that device is perfect while the others see a *center-cropped* slice. Either set `ini` for the device you use most and change + re-push when you switch, or **use LAN mode** instead (the plugin renders per-device on the fly, so it never crops).

### Autostart (remote board recovers after reboot)

For a stable long-term remote setup the key is not "start it once by hand" but "it comes back on its own after a reboot". Verified in practice: after the two steps below, within ~1 minute of a Windows reboot the bridge and pusher come back up automatically and the Kindle board recovers with no manual step.

1. **Bridge autostart**: put a shortcut to `workbuddy_bridge.vbs` into the Startup folder (`Win+R` → run `shell:startup`). After logon it auto-locates Python, frees port 8765, silently launches the bridge, and health-checks it via `ServerXMLHTTP`.
   - ⚠️ The bridge MUST run inside the user's interactive logon session — it needs to read `~/.workbuddy/workbuddy.db` to get the "space · task name". Run under SYSTEM / a session with no desktop and it can't read the DB, so task names degrade to browser-op names like "对话 / 上下文压缩". Use "start after logon"; do not make it a system-level service.
2. **Pusher autostart**: also put a shortcut to `publish_snapshot.vbs` into the Startup folder. It silently runs `publish_snapshot.py --loop` in the background and keeps pushing covers to the snapshot repo at `interval`.

> With both in the Startup folder, the whole chain (bridge renders → pusher uploads → Kindle pulls the raw URL) closes automatically after every boot — exactly the "still shows up after a reboot" state.

- The repo is Public: only someone with the URL can reach it, but **task names and your credit balance are drawn onto that PNG**. If that bothers you, use a sufficiently random repo name and set `push_status = false` in `publish.ini` to skip the JSON.

## FAQ

**Q: Why does the lock screen / dashboard image never update?**
A: First check the PC-side `bridge.log` for `REQ from <Kindle IP>`. None means the WiFi / hotspot link is down (Kindle blocks ICMP, so `ping` failing is normal); if present, the link is fine and the issue is on the render side.

**Q: The timestamp is frozen at an old time?**
A: The persistent board re-pulls the image every 3 minutes, so the timestamp (`SYNC <time>`) changes with it; if it doesn't, the bridge likely isn't receiving requests (see above).

**Q: The Kindle is unresponsive / only a reboot fixes it?**
A: An older build let device sleep swallow touches; that's now fixed by pausing auto-suspend while the board is up. Each refresh still pulls the cover synchronously on KOReader's single main thread, so the new build first does a 2-second TCP reachability probe: if the bridge is down it keeps the current cover and backs off for 60 seconds instead of freezing every 20 seconds.

**Q: `wb_cover_*.png` files pile up in the koreader directory?**
A: Every refresh writes a uniquely-named cover cache (KOReader memoises decoded bitmaps per path, so names can't be reused), and the previous one is removed. But after a plugin reload or crash the `_last_cover` pointer is lost, so old `EXPIRED` covers linger forever. The build now sweeps automatically at plugin start, on wake, and at the start of each refresh — it keeps only the picture on screen plus the one it just replaced (`ImageWidget` decodes lazily, so deleting too early makes the refresh silently fail) and reclaims everything else including `.tmp` scratch files; with no pointer left (i.e. right after a restart) it keeps the newest by mtime. To do it by hand: menu `WorkBuddy Monitor → 清理看板缓存 (删除失效封面)`, or bind the gesture `WorkBuddy 清理看板缓存`.

**Q: The credits number / `SYNC` time is frozen on a stale value?**
A: Work out which side is at fault first. Open `http://127.0.0.1:8765/status.json` on the PC: if `credits.remaining` and `updatedAt` are fresh, the bridge and scraping are fine and the problem is on the Kindle's display side. One defect that caused exactly this is now fixed — the auto-sweep used to delete the cover *while it was still being decoded* (`ImageWidget` decodes lazily/asynchronously, and a missing file makes the swap fail), so a freshly downloaded PNG was never shown. The build now deletes nothing right after a download; the sweep runs at the start of the next refresh and additionally protects `_prev_cover`. If it still doesn't refresh, fully quit and restart KOReader on the Kindle (the plugin must be reloaded to pick up new logic) and make sure `main.lua` in the plugin directory was actually overwritten.

**Q: The cover shows EXPIRED / an alert bar?**
A: The cookie expired — refresh `cookies.txt` as described in "What if the login expires".

**Q: I use a keypad-only Kindle (Kindle 3, no touchscreen) — how do I exit the board, and what resolution do I set?**
A: Exiting — once the board is up, press **any physical key**: the page-turn buttons, the 5-way directional keys, the 5-way center, or Back all dismiss it; no gesture required (tap / swipe / hold still work on touch devices).
Resolution — **in LAN mode you set nothing**: the plugin sends the device's own screen size to the bridge, which renders at exactly that size, so a K3 automatically gets 600×800 and a high-res Kindle gets its own resolution, each crisp and uncropped. Only **remote mode** pushes one fixed-size image whose dimensions come from `width` / `height` in your PC's `publish.ini` (the example defaults to `1072×1448`, tuned for Paperwhite-class hi-res devices): if `ini` is set to the hi-res `1072×1448` and you view the remote snapshot on a K3, you only see the *center 600×800 slice* of that larger image (cropped), not the whole board — and vice versa. So per the "What width/height to set per device" section above, set `ini` to the resolution of the device you mainly view the board on.

## License

[MIT](LICENSE) © RC-APC
