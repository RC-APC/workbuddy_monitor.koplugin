#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cyberpunk HUD status cover generator (PNG) for the WorkBuddy -> KOReader monitor.

Renders the agent-agnostic status JSON into a high-contrast "terminal/HUD" cover.

CRITICAL: target device is a grayscale Kindle e-ink panel, so color hue is invisible.
The default (mono=True) drops all hue and differentiates status by VALUE + SHAPE:
  - RUNNING : solid inverted chip (white fill, black text)  -> loudest, "active"
  - DONE    : white outline chip, white text               -> subtle, "settled"
  - QUEUED  : gray outline chip, gray text                 -> recessive
  - EXPIRING: fully inverted panel (white bg, black text)   -> alarm on e-ink
Progress = donut ring. 100% -> solid white ring fully filled; otherwise proportional.
Donut center = black disc, white "xx%" text. Frames/cursors = white.

A color mode (mono=False, via ?mono=0) is kept only for previewing on a PC/color
device; it is NOT what ships to the Kindle.

Three task layouts (task_layout=): "rows" | "grouped" | "hero".
Pure Pillow. Called by wb-bridge.py for the /cover.png route.
"""
import hashlib
import io
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_PATHS = [
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]
_FONT_PATH = None
for _p in FONT_PATHS:
    try:
        ImageFont.truetype(_p, 20)
        _FONT_PATH = _p
        break
    except Exception:
        continue


def _font(size):
    return ImageFont.truetype(_FONT_PATH, size)


# A fresh, random blessing is drawn next to the user's display name on every
# render, so the cover feels alive across refreshes. No emoji on purpose:
# the cover is rendered with a CJK font (simhei) on the PC and shipped as a
# grayscale PNG -- emoji glyphs would render as tofu boxes on e-ink.
_BLESSINGS = [
    "愿你今天也元气满满",
    "保持热爱，奔赴山海",
    "慢慢来，比较快",
    "今天的你也很努力呀",
    "好事正在发生",
    "深呼吸，一切都会好的",
    "小步快跑，静待花开",
    "愿你被这个世界温柔以待",
    "码到成功，bug 退散",
    "进度条在动，就很棒",
    "今天也要好好吃饭",
    "累了就歇会儿，正在充电",
    "你比昨天的自己更厉害",
    "前路漫漫亦灿灿",
    "心若安定，处处是归途",
    "保持好奇，保持自由",
    "所念皆所愿，所行化坦途",
    "温柔且坚定，知足且上进",
    "把日子过成自己喜欢的样子",
    "一切尽意，百事从欢",
]


# --- personal buddy pet -----------------------------------------------------
# Authentic Claude Code `/buddy` ASCII-art companions. Species art taken from
# ramarivera/coding-buddy (MIT) -- the project that revived `/buddy` -- so the
# cover pet looks EXACTLY like the terminal buddy: real monospace text, {E} is
# the eye glyph slot. Drawn in the otherwise-empty right side of the credits
# band; awake (° eyes) while a task runs, asleep (· eyes + Zzz) otherwise.
# Grayscale-safe: the sprite is plain light-on-dark text, no hue involved.
#
# WHICH SPECIES YOU GET IS DETERMINISTIC, not random: it is picked by hashing
# the user's stable WorkBuddy account UID (bridge -> status.userId), so the
# same user always sees the same buddy across refreshes while different users
# get different ones -- a per-user draw from the species below.

_BUDDY_ART = {
    "duck":     ["", "    __      ", "  <({E} )___  ", "   (  ._>   ", "    `--'    "],
    "goose":    ["", "     (°>    ", "     ||     ", "   _(__)_   ", "    ^^^^    "],
    "blob":     ["", "   .----.   ", "  ( {E}  {E} )  ", "  (      )  ", "   `----'   "],
    "cat":      ["", r"   /\_/\    ", r"  ( {E}   {E})  ", "  (  ω  )   ", '  (")_(")   '],
    "dragon":   ["", r"  /^\  /^\  ", " <  {E}  {E}  > ", " (   ~~   ) ", "  `-vvvv-'  "],
    "octopus":  ["", "   .----.   ", "  ( {E}  {E} )  ", "  (______)  ", r"  /\/\/\/\  "],
    "owl":      ["", r"   /\  /\   ", "  (({E})({E}))  ", "  (  ><  )  ", "   `----'   "],
    "penguin":  ["", "  .---.     ", "  ({E}>{E})     ", r" /(   )\    ", "  `---'     "],
    "turtle":   ["", "   _,--._   ", "  ( {E}  {E} )  ", r" /[______]\ ", "  ``    ``  "],
    "snail":    ["", " {E}    .--.  ", r"  \  ( @ )  ", r"   \_`--'   ", "  ~~~~~~~   "],
    "ghost":    ["", "   .----.   ", r"  / {E}  {E} \  ", "  |      |  ", "  ~`~``~`~  "],
    "axolotl":  ["", r"}~(______)~{", r"}~({E} .. {E})~{", "  ( .--. )  ", r"  (_/  \_)  "],
    "capybara": ["", "  n______n  ", " ( {E}    {E} ) ", " (   oo   ) ", "  `------'  "],
    "cactus":   ["", " n  ____  n ", " | |{E}  {E}| | ", " |_|    |_| ", "   |    |   "],
    "robot":    ["", "   .[||].   ", "  [ {E}  {E} ]  ", "  [ ==== ]  ", "  `------'  "],
    "rabbit":   ["", r"   (\__/)   ", "  ( {E}  {E} )  ", " =(  ..  )= ", '  (")__(")  '],
    "mushroom": ["", " .-o-OO-o-. ", "(__________)", "   |{E}  {E}|   ", "   |____|   "],
    "chonk":    ["", r"  /\    /\  ", " ( {E}    {E} ) ", " (   ..   ) ", "  `------'  "],
    "pikachu":  ["", r"   /\_/\   ", "  ({E} {E})  ", "   (  ω )   ", "   (__)    "],
    "wyvern":   ["}       {", r"|\^```^/|", r"\ {E}' '{E} /", " ≈(° °)≈", "   '-'"],
}


def _buddy_style_for(uid):
    """Deterministic species pick from the user id (md5, stable across runs)."""
    key = str(uid or "").strip() or "guest"
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
    return list(_BUDDY_ART.keys())[h % len(_BUDDY_ART)]


# The sprite must render with a real MONOSPACE font or the ASCII art falls
# apart (Proportional CJK fonts shift every glyph). Consolas first: it covers
# °, ω and ≈ and has the classic terminal look.
_MONO_FONT_PATHS = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "C:/Windows/Fonts/lucon.ttf",
]
_MONO_FONT = None
for _p in _MONO_FONT_PATHS:
    try:
        ImageFont.truetype(_p, 20)
        _MONO_FONT = _p
        break
    except Exception:
        continue


def _bfont(size):
    return ImageFont.truetype(_MONO_FONT or _FONT_PATH, size)


def _buddy_pet(d, cx, cy, fsize, awake, P, theme="dark", uid=None):
    """Draw the user's buddy as authentic `/buddy` ASCII art (monospace font),
    centred on (cx, cy). Awake: open °-eyes + a task running; asleep: drowsy
    ·-eyes and a Zzz drifting up-LEFT (the top-right corner hosts LIVE)."""
    art = _BUDDY_ART[_buddy_style_for(uid)]
    eye = "\u00b0" if awake else "\u00b7"
    lines = [ln.replace("{E}", eye) for ln in art]
    f = _bfont(fsize)
    lh = int(fsize * 1.18)
    widest = max(int(d.textlength(ln, font=f)) for ln in lines) or 1
    th = lh * len(lines)
    ox = int(cx - widest / 2)
    oy = int(cy - th / 2)
    for i, ln in enumerate(lines):
        if ln.strip():
            d.text((ox, oy + i * lh), ln, font=f,
                   fill=P["WHITE"] + (255,), anchor="la")
    if not awake:
        zc = P["LGRAY"]
        _text(d, (ox - 12, oy + 4), "z", 15, zc, anchor="la")
        _text(d, (ox - 24, oy - 10), "Z", 19, zc, anchor="la")
        _text(d, (ox - 38, oy - 26), "Z", 24, zc, anchor="la")



def _mono_palette():
    """Black background, white text -- the default Kindle cover."""
    return {
        "BG": (16, 16, 16), "WHITE": (238, 238, 238), "LGRAY": (168, 168, 168),
        "MGRAY": (120, 120, 120), "DGRAY": (66, 66, 66), "DARK": (14, 14, 14),
        "ACCENT": (238, 238, 238), "ACCENT2": (168, 168, 168),
        # INK = text drawn ON TOP of a filled "WHITE" block (the inverted
        # status chips / alarm bar). In dark mode that block is white so the
        # ink is black; in light mode the block is black so the ink is white.
        "INK": (10, 10, 10),
    }


def _mono_palette_inverted():
    """White background, black text.

    On e-ink this is genuinely easier to read for long text in daylight: the
    page is lit rather than glowing, and the glyphs are the darkest thing on
    the screen. Every accent colour has to be INVERTED too, otherwise the
    "inverted chip" status markers (a block in P["WHITE"]) would disappear
    into the page.
    """
    return {
        "BG": (247, 247, 247), "WHITE": (12, 12, 12), "LGRAY": (78, 78, 78),
        "MGRAY": (128, 128, 128), "DGRAY": (186, 186, 186), "DARK": (238, 238, 238),
        "ACCENT": (12, 12, 12), "ACCENT2": (78, 78, 78),
        "INK": (250, 250, 250),
    }


def _palette(mode="dark", color=False):
    if color:
        return _color_palette()
    return _mono_palette_inverted() if mode == "light" else _mono_palette()


def _color_palette():
    return {
        "BG": (8, 9, 18), "WHITE": (235, 246, 255), "LGRAY": (135, 146, 158),
        "MGRAY": (135, 146, 158), "DGRAY": (70, 82, 94), "DARK": (12, 14, 22),
        "ACCENT": (0, 229, 255), "ACCENT2": (255, 43, 214),
        "CYAN": (0, 229, 255), "GREEN": (60, 255, 140), "RED": (255, 64, 92),
        "YELLOW": (240, 220, 40), "INK": (10, 10, 10),
    }


def _status_style(st, mono, P):
    """Return dict(fg, bg, fill, text) for a status chip. Shape/value, not hue."""
    st = str(st).lower()
    if mono:
        if st == "running":
            return {"fg": P["WHITE"], "bg": P["WHITE"], "fill": True, "text": P["INK"]}
        if st == "done":
            return {"fg": P["WHITE"], "bg": P["BG"], "fill": False, "text": P["WHITE"]}
        return {"fg": P["MGRAY"], "bg": P["BG"], "fill": False, "text": P["MGRAY"]}
    if st == "running":
        c = P["CYAN"]
    elif st == "done":
        c = P["GREEN"]
    else:
        c = P["MGRAY"]
    return {"fg": c, "bg": P["DARK"], "fill": False, "text": c}


def _text(d, xy, s, size, fill, anchor="lt"):
    d.text(xy, s, font=_font(size), fill=fill, anchor=anchor)


def _neon(d, xy, s, size, fill, glow, anchor="lt", spread=3, alpha=70):
    f = _font(size)
    for dx in range(-spread, spread + 1):
        for dy in range(-spread, spread + 1):
            if dx == 0 and dy == 0:
                continue
            d.text((xy[0] + dx, xy[1] + dy), s, font=f,
                   fill=glow + (alpha,), anchor=anchor)
    d.text(xy, s, font=f, fill=fill + (255,), anchor=anchor)


def _chip_right(d, right_x, y, text, st, P, mono, size=22, h=34, pad=10):
    ss = _status_style(st, mono, P)
    f = _font(size)
    tw = d.textlength(text, font=f)
    x0 = right_x - tw - pad * 2
    d.rectangle([x0, y, right_x, y + h], fill=ss["bg"] + (255,),
                outline=ss["fg"] + (255,), width=2)
    d.text((x0 + pad, y + h // 2), text, font=f, fill=ss["text"] + (255,), anchor="lm")


def _chip_left(d, left_x, y, text, col, size=26, h=38, pad=14):
    f = _font(size)
    tw = d.textlength(text, font=f)
    d.rectangle([left_x, y, left_x + tw + pad * 2, y + h], fill=(14, 14, 14) + (255,),
                outline=col + (255,), width=2)
    d.text((left_x + pad, y + h // 2), text, font=f, fill=col + (255,), anchor="lm")


def _corner(d, cx, cy, sx, sy, bl, color):
    d.line([(cx, cy), (cx + sx * bl, cy)], fill=color + (255,), width=8)
    d.line([(cx, cy), (cx, cy + sy * bl)], fill=color + (255,), width=8)


def _warn_icon(d, x, y, size, color):
    s = size
    d.polygon([(x + s // 2, y), (x, y + s), (x + s, y + s)],
              outline=color + (255,), width=3)
    _text(d, (x + s // 2, y + s + 1), "!", 16, color, anchor="mt")


def _donut(d, cx, cy, r, prog, P, mono, ring_w=14, text_size=20, center_text=None):
    """Donut progress ring. 100% -> solid white ring; otherwise proportional.
    Center = black disc with white text (default 'xx%', can be credits used).
    A dark backing disc keeps the white ring visible even on an inverted card."""
    prog = max(0.0, min(1.0, prog))
    d.ellipse([cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
              fill=P["BG"] + (255,))                                     # backing
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, 0, 360, fill=P["DGRAY"] + (255,), width=ring_w)      # track
    if prog >= 0.999:
        d.arc(bbox, 0, 360, fill=P["WHITE"] + (255,), width=ring_w)  # full white ring
    else:
        d.arc(bbox, -90, -90 + prog * 360, fill=P["WHITE"] + (255,), width=ring_w)
    cr = r - ring_w // 2 - 2
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=P["BG"] + (255,))
    txt = center_text if center_text else f"{int(round(prog * 100))}%"
    _text(d, (cx, cy), txt, text_size, P["WHITE"], anchor="mm")


# ----- date / task filtering helpers ---------------------------------------

def _parse_date(t):
    for k in ("date", "updatedAt"):
        v = t.get(k)
        if not v:
            continue
        s = str(v)[:10]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
    return None


def _filter_tasks(tasks, max_recent_days=3, max_count=10, today=None):
    """Keep tasks whose date falls inside the last `max_recent_days` calendar
    days INCLUDING today (days=3 -> today, yesterday, the day before).
    Tasks without a parsable date are kept. Sorted newest first, then capped."""
    today = today or datetime.now()
    window = (today - timedelta(days=max_recent_days - 1)).date()  # inclusive
    kept = []
    for t in tasks:
        dd = _parse_date(t)
        if dd is None or dd.date() >= window:
            kept.append(t)
    kept.sort(key=lambda t: (_parse_date(t) or today), reverse=True)
    return kept[:max_count]


def _expire_date_str(e, today=None):
    ed = e.get("expireDate")
    if ed:
        return str(ed)[:10].replace("-", "/")
    dl = e.get("daysLeft")
    if dl is None:
        return "?"
    today = today or datetime.now()
    d = today + timedelta(days=int(dl))
    return d.strftime("%Y/%m/%d")


# ----- task row (compact + donut) ------------------------------------------

def _fmt_credits(c):
    """Compact credits string for the donut center: 3 -> '3c', 12.5 -> '12.5c'."""
    try:
        c = float(c)
    except Exception:
        return None
    if c >= 100:
        return "%dc" % int(round(c))
    if c == int(c):
        return "%dc" % int(c)
    return "%.1fc" % c


def _task_row(d, x0, xr, y, t, P, mono, max_cre=0.0, rh=66, name_size=26):
    """Single row: task name on the left, credit ring on the far right.

    The ring fill is RELATIVE to the biggest spender in view:
        max spender -> full white ring (100%)
        others      -> proportional, so 850c and 3c are clearly different
    The ring centre always shows the task's REAL cumulative credits, and the
    % next to the name is that same relative share, so nothing is distorted --
    the ring answers "which task cost the most", the number answers "how much".

    `rh` / `name_size` let the caller shrink rows so that EVERY task in the
    window fits instead of silently dropping the tail.

    Returns next y (y + rh).
    """
    # "空间名-任务名" when the task belongs to a real space (hyphen form per
    # user preference -- the old "空间 · 任务" middle-dot display read like a
    # browser-side name). Tasks with no meaningful space keep the bare client
    # title, matching the desktop sidebar.
    nm = str(t.get("name") or t.get("display") or "?")
    sp = str(t.get("space") or "").strip()
    name = "%s-%s" % (sp, nm) if sp and sp not in nm else nm
    st = str(t.get("status", "?")).lower()
    cre = t.get("credits")

    # ---- right: donut filled by share-of-the-biggest-spender ----
    R = max(14, int(rh * 0.45))
    rcx, rcy = xr - R, y + rh // 2
    if cre is not None and max_cre and max_cre > 0:
        share = min(float(cre) / float(max_cre), 1.0)
    else:
        share = 0.0
    center = _fmt_credits(cre) if cre is not None else "-"
    _donut(d, rcx, rcy, R, share, P, mono, ring_w=max(7, R // 3),
           text_size=max(10, int(R * 0.46)), center_text=center)

    # ---- left: status marker + name + relative share% ----
    my = y + rh // 2
    bh = max(14, int(rh * 0.38))
    # the running marker must be the STRONGEST contrast on the page, whatever
    # the theme: P["WHITE"] is the ink colour, so on the light (white bg)
    # theme it renders black, and on the dark theme it renders white. Using
    # the ink colour for the block is what makes the one live task pop.
    if st == "running":
        d.rectangle([x0 - 8, my - bh // 2, x0 + 8, my + bh // 2],
                    fill=P["WHITE"] + (255,))
    else:
        d.rectangle([x0 - 8, my - bh // 2, x0 + 8, my + bh // 2],
                    fill=(P["DGRAY"] if st == "done" else P["MGRAY"]) + (255,))
    pct_txt = "" if cre is None else "%d%%" % round(share * 100)
    f = _font(name_size)
    fp = _font(max(14, int(name_size * 0.76)))
    # the % sits just left of the ring, right-aligned on the name's baseline, so
    # it can never overlap the task name
    pw = d.textlength(pct_txt, font=fp) if pct_txt else 0
    px = rcx - R - 12
    avail = px - (x0 + 18) - (pw + 10 if pct_txt else 0)
    full = name
    while name and d.textlength(name, font=f) > avail:
        name = name[:-1]
    if name != full:
        name = name[:-1] + "…" if name else "…"
    _text(d, (x0 + 18, my), name, name_size,
          P["WHITE"] if st == "running" else P["LGRAY"], anchor="lm")
    if pct_txt != "":
        _text(d, (px, my), pct_txt, max(14, int(name_size * 0.76)),
              P["MGRAY"], anchor="rm")
    return y + rh


def _tasks_rows(d, x0, xr, y, tasks, P, mono, bottom_limit, max_cre=0.0):
    if not tasks:
        _text(d, (x0, y), "- none -", 26, P["MGRAY"], anchor="lt")
        return y + 40
    avail = max(40, bottom_limit - y)
    rh = int(min(66, max(34, avail // len(tasks)) - 4))
    nsize = int(min(26, max(15, rh * 0.40)))
    for t in tasks:
        if y + rh > bottom_limit + 1:
            break
        y = _task_row(d, x0, xr, y, t, P, mono, max_cre, rh, nsize) + 4
    return y


def _tasks_grouped(d, x0, xr, y, tasks, P, mono, bottom_limit, max_cre=0.0,
                   win_txt="今天"):
    """One flat table: name (left) ... credit ring (hard right).

    Row height is ADAPTIVE: whatever is left between here and the footer is
    divided by the number of tasks, so every task in the window is shown --
    a quiet day with 3 tasks gets comfortable rows, a busy 3-day window with 10
    gets tighter rows instead of silently dropping the tail.
    """
    if not tasks:
        _text(d, (x0, y), "- none -", 26, P["MGRAY"], anchor="lt")
        return y + 40
    # column header
    _text(d, (x0 + 18, y), "任务 (%s)" % win_txt, 20, P["MGRAY"], anchor="lt")
    _text(d, (xr, y), "圈=相对最高用量 / 内=累计积分", 18, P["MGRAY"], anchor="rt")
    y += 30
    d.line([(x0, y), (xr, y)], fill=P["DGRAY"] + (255,), width=2)
    y += 12
    avail = max(40, bottom_limit - y)
    # 66 is the comfortable row; below ~46 the ring + name stop being readable
    rh = int(min(66, max(34, avail // len(tasks)) - 4))
    nsize = int(min(26, max(15, rh * 0.40)))
    for t in tasks:
        if y + rh > bottom_limit + 1:
            break
        y = _task_row(d, x0, xr, y, t, P, mono, max_cre, rh, nsize) + 4
    return y


def _tasks_hero(d, x0, xr, y, tasks, P, mono, bottom_limit):
    if not tasks:
        _text(d, (x0, y), "- none -", 26, P["MGRAY"], anchor="lt")
        return y + 40
    running = [t for t in tasks if str(t.get("status", "")).lower() == "running"]
    primary = (running or tasks)[0]
    others = [t for t in tasks if t is not primary]
    st = str(primary.get("status", "?")).lower()
    prog = float(primary.get("progress", 0) or 0)
    ss = _status_style(st, mono, P)
    pct = int(round(prog * 100))

    card_y, card_h = y, 220
    if y + card_h > bottom_limit:
        # no room for the hero card; fall back to compact rows
        return _tasks_rows(d, x0, xr, y, tasks, P, mono, bottom_limit)
    if ss["fill"]:
        d.rectangle([x0, card_y, xr, card_y + card_h], fill=P["WHITE"] + (255,),
                    outline=P["WHITE"] + (255,), width=3)
        card_text = P["INK"]
    else:
        d.rectangle([x0, card_y, xr, card_y + card_h], fill=P["BG"] + (255,),
                    outline=P["WHITE"] + (255,), width=3)
        card_text = P["WHITE"]
    _text(d, (x0 + 26, card_y + 20), "ACTIVE TASK", 24, card_text, anchor="lt")
    _text(d, (x0 + 26, card_y + 56), str(primary.get("name", "?")), 40,
          card_text, anchor="lt")

    rcx, rcy = xr - 100, card_y + card_h // 2 + 4
    _donut(d, rcx, rcy, 72, prog, P, mono, ring_w=18, text_size=34)

    y = card_y + card_h + 26
    if y + 46 > bottom_limit:
        return y
    total = len(tasks)
    rn = len(running)
    dn = len([t for t in tasks if str(t.get("status", "")).lower() == "done"])
    _text(d, (x0, y), f"TOTAL {total}   RUNNING {rn}   DONE {dn}", 26,
          P["WHITE"], anchor="lt")
    y += 46
    for o in others:
        if y + 32 > bottom_limit:
            break
        os_ = str(o.get("status", "?")).lower()
        _chip_right(d, xr, y, os_.upper(), os_, P, mono, size=18, h=26, pad=8)
        _text(d, (x0 + 10, y), f"- {o.get('name', '?')}", 22, P["MGRAY"], anchor="lt")
        y += 32
    return y


def render_cover(status, w=1080, h=1440, task_layout="grouped", mono=True,
                 max_recent_days=3, max_count=10, exit_hint=True,
                 theme="dark"):
    """theme: "dark" = black bg / white text, "light" = white bg / black text.
    Both are grayscale and both ship as 8-bit "L" PNGs."""
    P = _palette(theme, color=not mono)
    # Render in the 1080x1440 DESIGN space (every hardcoded metric below assumes
    # it), then downscale to the requested (w, h) at the end. This keeps the
    # layout proportional on any device -- e.g. a 600x800 Kindle 3 no longer
    # shows "字大图小"; the old code baked fixed-size pixels that only fit
    # 1080x1440, so smaller targets got oversized text and a cramped layout.
    DW, DH = 1080, 1440
    img = Image.new("RGBA", (DW, DH), P["BG"] + (255,))
    d = ImageDraw.Draw(img)
    _ow, _oh = w, h          # requested output size, applied before save
    w, h = DW, DH            # body below draws in design coordinates

    # background grid
    step = 96
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(P["DGRAY"] + (110,)) if mono else ((22, 44, 56) + (110,)), width=1)
    for y2 in range(0, h, step):
        d.line([(0, y2), (w, y2)], fill=(P["DGRAY"] + (110,)) if mono else ((22, 44, 56) + (110,)), width=1)

    m = 30
    d.rectangle([m, m, w - m, h - m], outline=P["WHITE"] + (235,), width=6)
    d.rectangle([m + 12, m + 12, w - m - 12, h - m - 12],
                outline=P["LGRAY"] + (180,), width=2)
    for cx, cy in [(m, m), (w - m, m), (m, h - m), (w - m, h - m)]:
        _corner(d, cx, cy, 1 if cx == m else -1, 1 if cy == m else -1, 76, P["WHITE"])

    x0 = m + 46
    xr = w - m - 46
    y = m + 44

    # header
    if mono:
        _text(d, (x0, y), "WORKBUDDY", 66, P["WHITE"], anchor="lt")
    else:
        _neon(d, (x0, y), "WORKBUDDY", 66, P["WHITE"], P["ACCENT2"], anchor="lt")
    cur_x = x0 + d.textlength("WORKBUDDY", font=_font(66)) + 18
    d.rectangle([cur_x, y + 8, cur_x + 26, y + 66], fill=P["WHITE"] + (255,))
    y += 84
    # --- header sub-line -----------------------------------------------------
    # The personal greeting (display name + a fresh random blessing each render)
    # sits on the SAME baseline as the "// STATUS MONITOR" sub-title, i.e. it is
    # PARALLEL to the sub-title, and is RIGHT-ALIGNED so it is drawn DIRECTLY
    # ABOVE the SYNC timestamp (which is the next line, also right-aligned).
    sub_txt = "// STATUS MONITOR  -  AGENT-AGNOSTIC"
    if mono:
        _text(d, (x0, y), sub_txt, 26, P["LGRAY"], anchor="lt")
    else:
        _neon(d, (x0, y), sub_txt, 26, P["LGRAY"], P["LGRAY"],
              anchor="lt", spread=2, alpha=80)
    greet_name = (status.get("displayName") or "").strip()
    blessing = random.choice(_BLESSINGS)
    greet = (greet_name + "，" if greet_name else "") + blessing
    # keep the greeting clear of the sub-title on the left
    gf = _font(22)
    sub_w = d.textlength(sub_txt, font=_font(26))
    max_greet_w = (xr - 18) - (x0 + sub_w + 28)
    while greet and d.textlength(greet, font=gf) > max_greet_w and len(greet) > 1:
        # trim from the blessing tail, preserving "name，" when present
        if greet_name and greet.startswith(greet_name + "，"):
            greet = greet_name + "，…"
            break
        greet = greet[:-1]
    if mono:
        _text(d, (xr, y), greet, 22, P["LGRAY"], anchor="rt")
    else:
        _neon(d, (xr, y), greet, 22, P["LGRAY"], P["LGRAY"],
              anchor="rt", spread=2, alpha=80)
    y += 36
    upd = status.get("updatedAt", "?")
    _text(d, (xr, y), "SYNC " + str(upd), 22, P["MGRAY"], anchor="rt")
    y += 16
    d.line([(m + 12, y), (w - m - 12, y)], fill=P["WHITE"] + (160,), width=2)
    y += 40

    # ---- AUTH FAILURE ALARM (top, full-width inverted bar = loudest on e-ink)
    # A dead cookie shows frozen numbers that look like LIVE data, so we must
    # shout. noCookie (no cookies.txt / WB_COOKIE) is a softer config hint.
    cr_top = status.get("credits", {}) or {}
    if cr_top.get("authExpired"):
        if cr_top.get("noCookie"):
            amsg = "▲ 未找到 cookies.txt 请在桥接目录放置并填入"
        else:
            amsg = "▲ 登录已失效 请刷新 cookies.txt"
        ay = y + 2
        d.rectangle([m + 12, ay, w - m - 12, ay + 46],
                    fill=P["WHITE"] + (255,), outline=None)
        _text(d, ((x0 + xr) // 2, ay + 23), amsg, 24, P["INK"], anchor="mm")
        y = ay + 46 + 14

    # credits remaining
    cr = status.get("credits", {}) or {}
    live = cr.get("live", False)
    auth_expired = cr.get("authExpired", False)
    _text(d, (x0, y), "\u25c6 CREDITS", 30, P["WHITE"], anchor="lt")
    if auth_expired:
        # inverted alarm chip (white block + black ink) -- the loudest marker
        btxt = "EXPIRED"
        bf = _font(22)
        bw_ = d.textlength(btxt, font=bf) + 20
        d.rectangle([xr - bw_, y, xr, y + 30], fill=P["WHITE"] + (255,), outline=None)
        _text(d, (xr - 10, y + 15), btxt, 22, P["INK"], anchor="rm")
    else:
        _text(d, (xr, y + 4),
              "LIVE" if live else "SAMPLE", 22,
              P["WHITE"] if live else P["MGRAY"], anchor="rt")
    y += 48
    rem = cr.get("remaining", 0)
    if mono:
        _text(d, (x0, y), f"{rem:,.0f}", 122, P["WHITE"], anchor="lt")
    else:
        _neon(d, (x0, y), f"{rem:,.0f}", 122, P["WHITE"], P["LGRAY"], anchor="lt")
    _text(d, (x0 + 380, y + 26), "REMAINING", 24, P["MGRAY"], anchor="lt")
    _text(d, (x0 + 380, y + 58), "POINTS", 24, P["MGRAY"], anchor="lt")
    # personal buddy pet: authentic `/buddy` ASCII art (species deterministic
    # from the user_id), awake (° eyes) when at least one task is running,
    # asleep (· eyes + Zzz) otherwise. Fills the otherwise-empty right side of
    # the credits band. `fsize` is the MONOSPACE font size of the sprite.
    running_now = sum(
        1 for t in (status.get("tasks") or [])
        if str(t.get("status", "")).lower() == "running")
    _buddy_pet(d, xr - 80, y + 60, 22, running_now > 0, P, theme=theme,
               uid=status.get("userId"))
    y += 132

    # used / total + plan line
    used = cr.get("used", 0)
    total = cr.get("total", 0)
    plan = cr.get("plan", "") or "-"
    _text(d, (x0, y),
          f"已用 {used:,.0f} / 总量 {total:,.0f}   {plan}", 26, P["LGRAY"],
          anchor="lt")
    y += 44

    # live burn: mini 7-day bars + today / N-day totals
    usage = cr.get("usage") or {}
    daily = usage.get("daily") or {}
    if daily:
        days_keys = sorted(daily.keys())[-7:]
        vals = [daily.get(k, 0.0) for k in days_keys]
        vmax = max(vals) or 1.0
        bh, bw, gap = 46, 30, 12
        bx = x0 + 6
        by_base = y + bh
        for k, v in zip(days_keys, vals):
            hh = max(3, int(round(bh * (v / vmax))))
            top = by_base - hh
            d.rectangle([bx, top, bx + bw, by_base],
                        fill=(P["WHITE"] if v > 0 else P["DGRAY"]) + (255,))
            _text(d, (bx + bw // 2, by_base + 4), k[5:].replace("-", "/"),
                  14, P["MGRAY"], anchor="mt")
            bx += bw + gap
        y += bh + 26
        today_v = usage.get("today", 0.0)
        tot_v = usage.get("total", 0.0)
        ndays = usage.get("days", 7)
        _text(d, (x0, y),
              f"今日已用 {today_v:,.1f}   近{ndays}日共 {tot_v:,.1f} 积分",
              24, P["LGRAY"], anchor="lt")
        y += 40
    else:
        y += 4

    # ---- expiry: ONLY the next-7-day total (0 means 0; used-up packs with
    # amount=0 are already filtered out upstream and never counted) ----
    expiring = [e for e in (cr.get("expiring", []) or [])
                if (e.get("amount", 0) or 0) > 0]
    within7 = [e for e in expiring if (e.get("daysLeft", 99) or 99) <= 7]
    sum7 = round(sum((e.get("amount", 0) or 0) for e in within7), 2)
    y += 6
    _text(d, (x0, y), "◆ EXPIRY", 30, P["WHITE"], anchor="lt")
    y += 42
    if sum7 > 0:
        fg7 = P["INK"] if mono else P["RED"]
        if mono:
            d.rectangle([x0 - 6, y - 6, xr + 6, y + 34], fill=P["WHITE"] + (255,), outline=None)
        _text(d, (x0, y), f"▲ 未来7天到期: {sum7:,.0f} 积分", 27, fg7, anchor="lt")
    else:
        _text(d, (x0, y), "未来7天到期: 0 积分", 25, P["LGRAY"], anchor="lt")
    y += 40
    y += 14

    # tasks (filtered: last N days, capped, never past footer)
    tmeta = status.get("taskMeta") or {}
    # the window is adaptive (today, widened only if the day is too quiet),
    # so label whatever was actually used instead of a hard-coded number
    wd = int(tmeta.get("windowDays") or max_recent_days or 1)
    win_txt = "今天" if wd <= 1 else ("近%d天" % wd)
    _text(d, (x0, y), "\u25c6 TASKS  -  %s" % win_txt, 28,
          P["WHITE"], anchor="lt")
    # summary on the right of the same line: how many live / how many credits
    if tmeta.get("ok"):
        _text(d, (xr, y),
              "进行 %d / 共 %d 项 · 合计 %s 分" % (
                  tmeta.get("running", 0), tmeta.get("count", 0),
                  _fmt_credits(tmeta.get("totalCredits") or 0) or "0"),
              20, P["LGRAY"], anchor="rt")
    y += 48
    tasks = _filter_tasks(status.get("tasks", []) or [], max_recent_days, max_count)
    # the ring gauge is relative: the biggest spender in view is a full ring
    cres = [float(t.get("credits") or 0) for t in tasks if t.get("credits") is not None]
    maxcre = max(cres) if cres else 0.0
    bottom_limit = h - m - 80
    if task_layout == "grouped":
        y = _tasks_grouped(d, x0, xr, y, tasks, P, mono, bottom_limit, maxcre,
                           win_txt)
    elif task_layout == "hero":
        y = _tasks_hero(d, x0, xr, y, tasks, P, mono, bottom_limit)
    else:
        y = _tasks_rows(d, x0, xr, y, tasks, P, mono, bottom_limit, maxcre)

    # footer
    fy = h - m - 56
    d.line([(m + 12, fy - 18), (w - m - 12, fy - 18)], fill=P["WHITE"] + (150,), width=2)
    _text(d, (x0, fy),
          f"SYNC EVERY 3 MIN  -  SRC:{status.get('source', '?')}", 20, P["MGRAY"],
          anchor="lt")
    if exit_hint:
        # The exit affordance is DRAWN INTO the PNG, not added as a KOReader
        # widget: an extra TopContainer/Button with dimen=screen height pushed
        # the whole cover off-screen. A hint drawn into the image costs zero
        # layout and cannot push anything off. Tapping anywhere still exits.
        hf = _font(26)
        hx, hy = xr - 14, fy - 12
        d.rectangle([hx - 20, hy - 20, hx + 20, hy + 20],
                    fill=P["WHITE"] + (255,), outline=None)
        d.text((hx, hy), "✕", font=hf, fill=P["INK"] + (255,), anchor="mm")

    # IMPORTANT: ship an 8-bit GRAYSCALE ("L") PNG, not RGB(A). The destination
    # screen is 1-bit grayscale, so a grayscale PNG makes the blit a same-type
    # copy with no per-pixel colour conversion -- that is both the correct
    # format for the panel and the cheapest blit. Color mode (?mono=0) is a
    # PC-only preview and stays RGB.
    # downscale the design-space image to the requested device size
    # (proportional fit; no-op when w/h == 1080x1440)
    if (_ow, _oh) != (w, h):
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:        # Pillow < 9.1
            resample = Image.LANCZOS
        img = img.resize((_ow, _oh), resample)

    if mono:
        out = img.convert("L")
        try:
            out = ImageOps.autocontrast(out, cutoff=0)
        except Exception:
            pass
    else:
        out = img.convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _wrap(d, text, font, max_w):
    """Greedy char-level wrap (CJK-safe: breaks per glyph, honours \n)."""
    out = []
    for para in str(text).split("\n"):
        line = ""
        for ch in para:
            test = line + ch
            if d.textlength(test, font=font) > max_w and line:
                out.append(line)
                line = ch
            else:
                line = test
        out.append(line)
    return out




if __name__ == "__main__":
    today = datetime.now()

    def dstr(off):
        return (today - timedelta(days=off)).strftime("%Y-%m-%d")

    sample = {
        "source": "workbuddy",
        "updatedAt": today.strftime("%Y-%m-%d %H:%M:%S"),
        "displayName": "Cong",
        "credits": {
            "remaining": 5335,
            "used": 2553,
            "total": 7889,
            "plan": "体验版",
            "cycle": {"expireDate": "2026-10-31", "daysLeft": 28, "amount": 2801},
            "expiring": [
                {"amount": 300, "expireDate": "2026-10-18", "daysLeft": 15},
                {"amount": 120, "expireDate": "2026-11-02", "daysLeft": 30},
            ],
            "usage": {"daily": {"2026-09-28": 206.15, "2026-09-29": 143.8,
                                "2026-09-30": 169.87, "2026-10-01": 16.46,
                                "2026-10-02": 63.61, "2026-10-03": 3.07},
                      "today": 3.07, "total": 801.82, "days": 7},
            "live": False,
        },
        "tasks": [
            {"name": "APK 改 DPI", "status": "running", "progress": 0.62, "date": dstr(0)},
            {"name": "导出病历 PDF", "status": "done", "progress": 1.0, "date": dstr(1)},
            {"name": "Kindle 监控插件", "status": "running", "progress": 0.35, "date": dstr(0)},
            {"name": "整理网盘", "status": "done", "progress": 1.0, "date": dstr(2)},
            {"name": "微信读书适配", "status": "queued", "progress": 0.0, "date": dstr(3)},
            {"name": "旧任务A", "status": "done", "progress": 1.0, "date": dstr(5)},
            {"name": "无日期任务", "status": "running", "progress": 0.78},
        ],
    }
    for layout in ("rows", "grouped", "hero"):
        fn = "cover_%s_mono.png" % layout
        with open(fn, "wb") as f:
            f.write(render_cover(sample, task_layout=layout, mono=True))
        print("wrote", fn)
