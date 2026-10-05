[English](README_EN.md)

# WorkBuddy KOReader Monitor

把 [WorkBuddy](https://workbuddy.cn) 智能体的 **积分余额 / 任务进度**，实时投到 **Kindle / KOReader 墨水屏**上，做成一个**常驻看板**。电脑端跑一个仅用标准库的小桥（HTTP 服务），Kindle 端装一个 KOReader 插件，两者用局域网通信。

> 适用场景：你有一台吃灰的 Kindle，想在墨水屏上随时看到「这个月积分还剩多少、哪些任务在跑、哪些快到期」——不点亮手机、不打开电脑，翻一眼就行。

## 功能特性

- **常驻看板**：Kindle 上常驻显示，每 **3 分钟**自动刷新（从桥重新拉 PNG，时间戳同步更新，不会冻住）。
- **双配色**：深（`theme=dark` 黑底白字）/ 浅（`theme=light` 白底黑字）两套，均为墨水屏安全灰度。
- **三个可绑手势**：`WorkBuddy 常驻看板`（开关）/ `WorkBuddy 设置休眠壁纸` / `WorkBuddy 退出常驻`。
- **锁屏封面**：点过「设置休眠壁纸」后，看板每刷新一次就把最新一张复制进 `wb_ss/cover.png`；你只需在 KOReader 里把锁屏指向该文件夹，锁屏即随之更新。
- **离线兜底**：桥抓不到实时数据时，回退到静态 `credits.json` / `tasks.json`，屏上永不空白。
- **防休眠干扰**：常驻期间暂停 Kindle 自动待机，避免「点不动 / 只能重启」。
- **登录失效报警**：Cookie 过期时，封面顶部出现全宽反白报警条「▲ 登录已失效 请刷新 cookies.txt」，`CREDITS` 徽标变反白 `EXPIRED`，积分数保留最后已知值并明确标记为失效态；PC 端双击启动器时还会弹窗提醒。
- **任务名带空间**：属于某个工作空间的活跃任务，封面上显示为 `空间名-任务名`（无空间的任务显示原名）。
- **今日已用**：Kindle 文字板额外显示 `TODAY USED: X credits`，与 WorkBuddy 界面口径对齐。

## 架构

```
 WorkBuddy 网页 (workbuddy.cn)
        │ cookies.txt（浏览器登录后的 Cookie）
        ▼
  ┌─────────────────────┐
  │  PC 桥  wb-bridge.py │  监听 0.0.0.0:8765（仅标准库 + Pillow）
  │   · /status.json     │
  │   · /cover.png       │  ← 用 Pillow 把状态渲染成 8 位灰度 PNG
  └─────────┬───────────┘
            │  WiFi 局域网
            ▼
  ┌─────────────────────┐
  │  Kindle KOReader     │  workbuddy_monitor.koplugin
  │   · 常驻看板(每3分钟) │
  │   · 锁屏封面(wb_ss/)  │
  └─────────────────────┘
```

## 目录结构

```
workbuddy-koreader-monitor/
├── workbuddy_monitor.koplugin/   # Kindle 端 KOReader 插件
│   ├── main.lua                  #   插件主体（看板/手势/锁屏）
│   ├── config.txt                #   第1行填桥地址，可选 theme=dark|light
│   └── _meta.lua                 #   插件元信息
├── wb-bridge.py                  # 电脑端桥（HTTP 服务，仅标准库 + Pillow）
├── cover_gen.py                  # PNG 渲染（Pillow）
├── fetch_credits.py              # 抓 WorkBuddy 实时积分（需 cookies.txt）
├── wb_sessions.py                # 读 WorkBuddy 本地会话库（任务列表）
├── parse_usage.py / scan_tasks.py# 其它数据源
├── deploy_to_kindle.py           # 部署插件到 Kindle（delete-first + 校验）
├── workbuddy_bridge.vbs          # Windows 启动器（双击即起，含健康检查+失效弹窗）
├── cookies.txt.example           # cookies.txt 模板与取 cookie 说明
├── credits.example.json          # 静态积分模板
├── tasks.example.json            # 静态任务模板
├── assets/                       # 示例封面图（深/浅配色）
└── README.md / README_EN.md      # 中英文文档
```

> ⚠️ 已废弃的旧启动器 `run_bridge.bat` / `bridge_watchdog.bat` / `_smoke_lua.py` 不再随仓库分发，统一用 `workbuddy_bridge.vbs`。

## 安装

### 1. 电脑端桥（Windows / macOS / Linux，Python 3.8+，需 Pillow）

```bash
cd workbuddy-koreader-monitor
pip install pillow          # 仅此一个第三方依赖
python wb-bridge.py         # 监听 0.0.0.0:8765
```

**最简单（Windows）**：直接双击 `workbuddy_bridge.vbs` —— 它会自动找到本机 Python、释放被占用的 8765 端口、静默拉起桥，并用 `ServerXMLHTTP`（绕过系统代理对 127.0.0.1 的劫持）做健康检查，最后弹一个确认框。

- 默认读 `credits.json` / `tasks.json`（用 `credits.example.json` / `tasks.example.json` 复制改名即可）。
- **实时积分**：在目录里放一个 `cookies.txt`（WorkBuddy 网页登录后的 Cookie），桥会自动抓**实时积分**与**今日已用**；Cookie 失效时自动回退静态数据并在封面报警。详见 `cookies.txt.example`。
- 可选鉴权：环境变量 `WB_TOKEN=xxx`，桥会要求 `Authorization: Bearer xxx`。

### 2. Kindle 端插件

把 Kindle 用 USB 挂到电脑（Windows 通常是一个盘符，脚本默认 `F:/`），然后：

```bash
python deploy_to_kindle.py          # 最多等 30 分钟，待 KOReader 释放文件锁后写入并逐字节校验
python deploy_to_kindle.py --once   # 只试一次
```

插件会出现在 KOReader 的「插件」菜单里。**装完重启一次 KOReader。**

### 3. 配置桥地址

编辑 `workbuddy_monitor.koplugin/config.txt` 第 1 行，填电脑的桥地址：

```
http://192.168.137.1:8765     # 电脑开热点时（手机/电脑共享热点给 Kindle）
http://192.168.1.20:8765      # 同路由器时，填 PC 的 LAN IP
```

> 同一 WiFi 下的 IP 是 DHCP 动态分配的，重连 / 休眠唤醒 / 路由器重启后可能变化；变了就在 PC 上 `ipconfig` 查 WLAN 的 IPv4 重新填并重新部署。KOReader 插件菜单里改过的地址优先级高于 `config.txt`。

### 4. 绑定手势（可选但推荐）

KOReader：`设置 → 手势 → 添加手势 → 画一个手势 → 动作列表`里选：
- **WorkBuddy 常驻看板**（再触发一次即退出，相当于开关）
- **WorkBuddy 设置休眠壁纸**
- **WorkBuddy 退出常驻**

### 5. 锁屏封面（可选）

插件菜单「锁屏封面文件 → 查看位置与说明」会显示 `wb_ss/cover.png` 的绝对路径。
在 KOReader：`设置 → 屏幕 → 锁屏类型 = 随机图片`，`锁屏图片文件夹 =` 上面的 `wb_ss` 文件夹。
点过「设置休眠壁纸」后，看板每次刷新都会把最新一张复制进去，锁屏即自动更新。

## 登录失效了怎么办（重要）

Cookie 是会话凭证，会过期（几天到几十天不等）。过期后桥**无法再静默假装正常**——它会明确报警：

- **Kindle 封面**：顶部全宽反白报警条 `▲ 登录已失效 请刷新 cookies.txt`；`CREDITS` 徽标从 `LIVE` 变反白 `EXPIRED`；积分数保留最后已知值但明显是失效态。
- **PC 端**：双击 `workbuddy_bridge.vbs` 启动后，若检测到失效会弹黄色警告框，提示更新 `cookies.txt`。

恢复步骤（约 1 分钟）：
1. 浏览器重新登录 `workbuddy.cn`（退出再登 / 等会话续期）。
2. **取新 Cookie**：F12 → Network（网络）→ 刷新页面 → 点任意发往 `workbuddy.cn` 的请求 → 右侧 Headers → Request Headers → 找到 `cookie:` 那一行 → **右键 → Copy value**（复制整串）。
3. 打开 `cookies.txt`，**只把第 1 行整行替换为新串**保存（文件里 `#` 开头的注释行会被自动忽略）。
4. **双击 `workbuddy_bridge.vbs`** 重启桥接。封面报警条消失、徽标回到 `LIVE`、积分数重新跳动即恢复成功（Kindle 每 3 分钟自动刷新）。

> 不要从「右击 → Copy as cURL」里摘 cookie——能用，但不如上面方法 1 干净。桥接**只认 `cookies.txt` 文件**，不再读 `WB_COOKIE` 环境变量。

## 开机自启（电脑端桥）

- **登录后自启**：把 `workbuddy_bridge.vbs` 快捷方式放进「启动」文件夹（Shell: `shell:startup`），登录后静默拉起桥。
- **崩溃自愈**：可用 Windows 计划任务，触发器「登录时」调用该 vbs；或定时每 5 分钟检查 8765 端口（用 `powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen"` 判断）未监听则重启。
- ⚠️ 以上均使用**交互登录令牌**，即**用户登录之后**桥才会起来（≤1 分钟），不是登录前的系统级服务。若要「开机即启（含锁屏前）」，把计划任务改成 **SYSTEM 账户 + 启动触发器**。

## 隐私与凭据

以下文件含凭据 / 个人数据，**已写入 `.gitignore`，绝不会进仓库**：

`cookies.txt` · `credits_cache.json` · `config.js` · `index.js` · `plans_usage.html` · `wb_account.json` · `bridge*.log`

桥默认只监听局域网；可选 `WB_TOKEN` 做简单 Bearer 鉴权。Cookie 仅用于本地拉取你自己的 WorkBuddy 数据，不上传任何第三方。

## 常见问题

**Q：为什么锁屏 / 看板图一直不更新？**
A：先看电脑端 `bridge.log` 里有没有 `REQ from <Kindle IP>`。没有说明是 WiFi / 热点不通（Kindle 禁 ICMP，`ping` 不通是正常的）；有则说明链路通，问题在渲染侧。

**Q：时间戳冻在旧时间？**
A：常驻看板每 3 分钟主动重新拉图，时间戳（`SYNC <时间>`）会跟着变；若不变，多半是桥没收到请求（见上）。

**Q：Kindle 上点不动 / 只能重启？**
A：旧版曾因设备休眠吞掉触摸导致，现已在常驻期间暂停自动待机解决。若仍有偶发卡顿：每次自动刷新都会在 Kindle 主线程同步拉取封面图（KOReader 单线程限制），桥不可达时会阻塞数秒。新版本在下载前先做一次 2 秒 TCP 可达性探测——桥没响应就直接保留上一张图并拉长退避（60 秒），不再每 20 秒冻结一次；PC 端桥恢复后下次刷新自动续上。

**Q：Kindle 的 koreader 目录里堆了一堆 `wb_cover_*.png` 失效封面，怎么清？**
A：每次刷新都会生成唯一命名的封面缓存（`KOReader` 按路径缓存解码图，不能复用文件名），正常只保留上一张、删前一张；但**插件重载 / 崩溃后 `_last_cover` 指针丢失，旧的 EXPIRED 封面就会永久残留**。新版本会在**插件启动、唤醒、以及每次成功刷新后自动清理**——只保留当前（或重启后最新）那张，其余连同 `.tmp` 半成品一并删除。也可手动清理：菜单 `WorkBuddy Monitor → 清理看板缓存 (删除失效封面)`，或绑定手势 `WorkBuddy 清理看板缓存`，会提示删除了几个文件。

**Q：封面显示 EXPIRED / 报警条？**
A：Cookie 过期了，按上面「登录失效了怎么办」刷新 `cookies.txt` 即可。

## License

[MIT](LICENSE) © RC-APC
