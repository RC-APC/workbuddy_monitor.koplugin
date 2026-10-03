# Load main.lua in a real Lua VM (lupa) with KOReader stubs and smoke-test
# the dashboard enter/exit paths, especially the "exit does not stick" bug.
import os, sys, types

import lupa

LUA_DIR = r"D:/kual_deliver/workbuddy-koreader-monitor/workbuddy_monitor.koplugin"
MAIN = os.path.join(LUA_DIR, "main.lua")


def build_vm():
    lua = lupa.LuaRuntime(unpack_returned_tuples=False)
    g = lua.globals()

    # ---- stubs -----------------------------------------------------------
    shown = []      # widget stack (what the user would see)
    scheduled = []  # (delay, fn)

    class Obj(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def make_extend(registry):
        def extend(base, table=None):
            name = "Widget"
            cls = {"__index": None}

            def new(_cls=None, inst=None):
                inst = dict(inst or {})
                obj = lua.table_from(inst) if False else None
                return inst
            return None
        return extend

    # Simpler: use Lua tables with __index for the widget classes.
    lua.execute("""
        function _mkclass(name)
            local c = {}
            c.__index = c
            c._name = name
            function c:extend(t)
                local k = {}
                for kk, vv in pairs(t or {}) do k[kk] = vv end
                k.__index = k
                setmetatable(k, { __index = c })
                return k
            end
            function c:new(t)
                local o = {}
                for kk, vv in pairs(t or {}) do o[kk] = vv end
                setmetatable(o, self)
                if o.init then o:init() end
                return o
            end
            return c
        end
    """)

    lua.execute("_G.__shown = {}")
    lua.execute("_G.__sched = {}")

    def preload(name):
        code = "return _mkclass(%r)" % name
        return code

    # package.preload stub: any require() returns a fresh fake class
    lua.execute("""
        package.preload = package.preload or {}
        package.loaded = package.loaded or {}
        setmetatable(package.preload, {
            __index = function(t, k)
                return function() return _mkclass(k) end
            end
        })
    """)

    # UIManager stub
    lua.execute("""
        UIManager = {
            _window_stack = {},
            show = function(self, w)
                if w then
                    table.insert(self._window_stack, w)
                    __shown[#__shown + 1] = w
                    w._shown = true
                end
            end,
            close = function(self, w)
                if not w then return end
                for i = #self._window_stack, 1, -1 do
                    if self._window_stack[i] == w then
                        table.remove(self._window_stack, i)
                        w._shown = false
                    end
                end
            end,
            unschedule = function(self, f) end,
            scheduleIn = function(self, sec, f)
                table.insert(__sched, { sec = sec, fn = f })
                return f
            end,
            setDirty = function(self, w, t) end,
            forceRePaint = function(self) end,
        }
    """)

    # Device stub
    lua.execute("""
        Device = {
            screen = {
                getWidth = function() return 1072 end,
                getHeight = function() return 1448 end,
                getSize = function() return { w = 1072, h = 1448, x = 0, y = 0 } end,
            },
        }
    """)

    # G_reader_settings stub
    lua.execute("""
        G_reader_settings = {
            _s = {},
            readSetting = function(self, k) return self._s[k] end,
            saveSetting = function(self, k, v) self._s[k] = v end,
        }
    """)

    # Font / logger / GestureRange stubs
    lua.execute("""
        Font = { getFace = function(self, n, s) return { name = n, size = s } end }
        logger = { dbg = function(...) end, warn = function(...) end, info = function(...) end }
    """)

    # Fake network: configurable behaviour
    lua.execute("""
        __net = { mode = "ok" }   -- "ok" | "fail" | "slow_exit"
        socket = { http = {
            request = function(arg)
                if __net.mode == "fail" then return nil, "timeout" end
                if type(arg) == "table" then
                    -- image download: write a fake PNG to the sink file
                    if __net.mode == "slow_exit" then
                        __exit_during_download()
                    end
                    return 1, 200
                end
                return '{"ok": true}', 200
            end,
            TIMEOUT = 8,
        } }
        ltn12 = { sink = { file = function(f)
            return function(chunk)
                if chunk then __sink_bytes = (__sink_bytes or 0) + #chunk end
                return true
            end
        end } }
        package.preload["socket.http"] = function() return socket.http end
        package.loaded["socket.http"] = socket.http
        package.preload["ltn12"] = function() return ltn12 end
        package.loaded["ltn12"] = ltn12
        package.preload["ui/widget/textwidget"] = function() return _mkclass("TextWidget") end
        package.preload["ui/widget/verticalgroup"] = function() return _mkclass("VerticalGroup") end
        package.preload["ui/widget/infomessage"] = function() return _mkclass("InfoMessage") end
        package.preload["ui/widget/imagewidget"] = function() return _mkclass("ImageWidget") end
        package.preload["ui/widget/centercontainer"] = function() return _mkclass("CenterContainer") end
        package.preload["ui/widget/container/widgetcontainer"] = function() return _mkclass("WidgetContainer") end
        package.preload["ui/widget/container/inputcontainer"] = function() return _mkclass("InputContainer") end
        package.preload["ui/widget/container/topcontainer"] = function() return _mkclass("TopContainer") end
        package.preload["ui/gesturerange"] = function() return _mkclass("GestureRange") end
        package.preload["ui/uimanager"] = function() return UIManager end
        package.loaded["ui/uimanager"] = UIManager
        package.preload["ui/font"] = function() return Font end
        package.preload["logger"] = function() return logger end
        package.preload["device"] = function() return Device end
        package.preload["datastorage"] = function() return { getDataDir = function() return __tmpdir end } end
        package.preload["json"] = function() return { decode = function(s) return { ok = true } end } end
        __pluginshare = {}
        package.preload["pluginshare"] = function() return __pluginshare end
        package.loaded["pluginshare"] = __pluginshare
        __actions = {}
        Dispatcher = {
            registerAction = function(self, name, value)
                __actions[name] = value
                return true
            end,
            removeAction = function(self, name) __actions[name] = nil end,
        }
        package.preload["dispatcher"] = function() return Dispatcher end
        package.loaded["dispatcher"] = Dispatcher
    """)

    lua.execute("""
        function __wb_count()
            local n = 0
            for _, w in ipairs(UIManager._window_stack) do
                if w and w._wb_board then n = n + 1 end
            end
            return n
        end
    """)

    lua.execute("__tmpdir = %r" % (LUATMP := r"D:/kual_deliver/workbuddy-koreader-monitor/_luatmp"))
    os.makedirs(LUATMP, exist_ok=True)
    # pre-create a valid cached PNG so the "keep last good cover" path can run
    import struct, zlib
    def png(path):
        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
        raw = b"\x00\x00"
        data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
        open(path, "wb").write(data)
    png(os.path.join(LUATMP, "wb_cover.png"))
    return lua, g


lua, g = build_vm()

# load the plugin
src = open(MAIN, encoding="utf-8").read()
lua.execute("__P = nil")
lua.execute("""
    local fn, e = load(%r, "main.lua")
    if not fn then __load_err = e; return end
    local ok, mod = pcall(fn)
    if not ok then __load_err = tostring(mod); return end
    _G.__P = mod
    __load_err = nil
""" % src)
err = lua.eval("__load_err")
if err:
    print("SYNTAX/LOAD ERROR:", err)
    sys.exit(1)
print("SYNTAX_OK / plugin loaded")

# instantiate
lua.execute("""
    _G.P = __P:new{ path = %r }
    _G.menu = {}
    P.ui = { menu = { registerToMainMenu = function(self, plugin) end,
                      updateItems = function() end } }
    P:init()
    __shown = {}
""" % LUA_DIR)
print("init OK; shown after init:", lua.eval("#__shown"))

# --- 1. menu items -------------------------------------------------------
lua.execute("""
    local items = {}
    P:addToMainMenu(items)
    __labels = {}
    for _, it in ipairs(items.workbuddy_monitor.sub_item_table) do
        __labels[#__labels + 1] = it.text
    end
""")
labels = [lua.eval("__labels")[i] for i in range(1, int(lua.eval("#__labels")) + 1)]
print("MENU:", labels)
assert not any("快捷键" in l for l in labels), "hotkey menu item still present!"

# --- 2. enter dashboard, then exit (normal) ------------------------------
lua.execute("""
    __net.mode = "ok"
    __shown = {}
    P:startDashboard()
    __on_screen = __wb_count()
""")
print("after startDashboard: stack =", lua.eval("__on_screen"))
assert lua.eval("__on_screen") >= 1

lua.execute("P:exitDashboard()")
print("after exitDashboard: boards =", lua.eval("__wb_count()"),
      "active_widget =", lua.eval("tostring(P.active_widget)"))
assert lua.eval("__wb_count()") == 0, "board not closed!"

# --- 3. exit DURING a blocking download (the reported bug) ---------------
lua.execute("""
    __net.mode = "slow_exit"
    _G.__exit_during_download = function()
        -- user taps exit while the UI is frozen in http.request
        P:exitDashboard()
    end
    __shown = {}
    UIManager._window_stack = {}
    P:startDashboard()
    __on_screen_after_slow = __wb_count()
""")
print("exit-during-download: stack =", lua.eval("__on_screen_after_slow"))
assert lua.eval("__on_screen_after_slow") == 0, "late widget re-opened the board!"

# --- 4. delayed sweeps must not resurrect anything -----------------------
lua.execute("""
    __net.mode = "ok"
    UIManager._window_stack = {}
    P:startDashboard()
    P:exitDashboard()
    for _, s in ipairs(__sched) do pcall(s.fn) end
    __after_sweeps = __wb_count()
""")
print("after sweeps: stack =", lua.eval("__after_sweeps"))
assert lua.eval("__after_sweeps") == 0

# --- 5. transient bridge failure keeps the last good cover ---------------
lua.execute("""
    __net.mode = "ok"
    UIManager._window_stack = {}
    P:startDashboard()
    __net.mode = "fail"
    __sched = {}
    P:_autoRefresh(P.active_widget)
    __after_fail = __wb_count()
    __fail_timer = (#__sched > 0)
""")
print("transient failure: stack still =", lua.eval("__after_fail"),
      "| retry scheduled =", lua.eval("__fail_timer"))
assert lua.eval("__after_fail") == 1, "cover was blanked on a transient failure!"
assert lua.eval("__fail_timer") == True

# --- 6. always-on mode must stop the device from suspending ---------------
# (the autosuspend plugin ignores screensaver_type -- see crash.log 22:44)
lua.execute("""
    __net.mode = "ok"
    UIManager._window_stack = {}
    G_reader_settings:saveSetting("auto_suspend_timeout_seconds", 900)
    __pluginshare.pause_auto_suspend = nil
    P:startDashboard()
    __as_on  = G_reader_settings:readSetting("auto_suspend_timeout_seconds")
    __ps_on  = tostring(__pluginshare.pause_auto_suspend)
    P:exitDashboard()
    __as_off = G_reader_settings:readSetting("auto_suspend_timeout_seconds")
    __ps_off = tostring(__pluginshare.pause_auto_suspend)
""")
print("autosuspend: while on =", lua.eval("__as_on"), "/", lua.eval("__ps_on"),
      "| after exit =", lua.eval("__as_off"), "/", lua.eval("__ps_off"))
assert lua.eval("__as_on") == 0, "auto-suspend not disabled while dashboard is on!"
assert lua.eval("__ps_on") == "true"
assert lua.eval("__as_off") == 900, "user's auto-suspend timeout not restored!"
assert lua.eval("__ps_off") == "nil"

# --- 7. gesture actions registered + toggle behaviour ---------------------
lua.execute("""
    __net.mode = "ok"
    UIManager._window_stack = {}
    __act_keys = {}
    for k, v in pairs(__actions) do __act_keys[#__act_keys + 1] = k end
    __act_ev1 = (__actions.workbuddy_dashboard or {}).event
    __act_ev2 = (__actions.workbuddy_dashboard_exit or {}).event
    -- gesture 1 -> open
    P:onWorkBuddyDashboard()
    __g1 = __wb_count()
    -- gesture 1 again -> close (toggle)
    P:onWorkBuddyDashboard()
    __g2 = __wb_count()
    -- gesture 2 -> explicit exit
    P:onWorkBuddyDashboard()
    P:onWorkBuddyExitDashboard()
    __g3 = __wb_count()
""")
acts = [lua.eval("__act_keys")[i] for i in range(1, int(lua.eval("#__act_keys")) + 1)]
print("dispatcher actions:", acts, "| events:",
      lua.eval("tostring(__act_ev1)"), lua.eval("tostring(__act_ev2)"))
print("gesture: open =", lua.eval("__g1"), "| toggle-close =", lua.eval("__g2"),
      "| explicit exit =", lua.eval("__g3"))
assert "workbuddy_dashboard" in acts and "workbuddy_dashboard_exit" in acts
assert lua.eval("__act_ev1") == "WorkBuddyDashboard"
assert lua.eval("__g1") == 1 and lua.eval("__g2") == 0 and lua.eval("__g3") == 0

print("ALL SMOKE TESTS PASSED")
