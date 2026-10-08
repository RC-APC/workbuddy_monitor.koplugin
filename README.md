[English](README_EN.md)

# WorkBuddy KOReader Monitor

把 [WorkBuddy](https://workbuddy.cn) 智能体的 **积分余额 / 任务进度**，实时投到 **Kindle / KOReader 墨水屏**上，做成一个**常驻看板**。电脑端跑一个仅用标准库的小桥（HTTP 服务），Kindle 端装一个 KOReader 插件——**同一 WiFi 下局域网直连**，或**走 GitHub 快照实现跨网络远程查看**（Kindle 出门在外也能看）。

> 适用场景：你有一台吃灰的 Kindle，想在墨水屏上随时看到「这个月积分还剩多少、哪些任务在跑、哪些快到期」——不点亮手机、不打开电脑，翻一眼就行。

## 功能特性

- **常驻看板**：Kindle 上常驻显示，每 **3 分钟**自动刷新（从桥重新拉 PNG，时间戳同步更新，不会冻住）。
- **双配色**：深（`theme=dark` 黑底白字）/ 浅（`theme=light` 白底黑字）两套，均为墨水屏安全灰度。
- **三个可绑手势**：`WorkBuddy 常驻看板`（开关）/ `WorkBuddy 设置休眠壁纸` / `WorkBuddy 退出常驻`。
- **按键机也能用**：Kindle 3 等无触屏设备，进看板后按**任意物理键**（机身翻页键 / 5-way 方向键 / 返回键）即退出，无需手势。
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
├── publish_snapshot.py           # 远程快照推送（局域网外也能看，见「远程查看」）
├── publish_snapshot.vbs          # 推送启动器（双击后台静默常驻 --loop）
├── publish.ini.example           # 远程快照配置模板（复制为 publish.ini 填写）
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

`cookies.txt` · `credits_cache.json` · `config.js` · `index.js` · `plans_usage.html` · `wb_account.json` · `bridge*.log` · `publish.ini`

桥默认只监听局域网。Cookie 仅用于本地拉取你自己的 WorkBuddy 数据，不上传任何第三方。

## 远程模式（跨网络，推荐）

**远程模式**适合「Kindle 和 PC 不在同一 WiFi、或出门在外也想看看板」的场景：PC 定时把渲染好的封面推送到云端，Kindle 读一个固定的 https 地址，两端不必在同一网络。相比局域网直连，它免公网 IP / 端口映射 / 内网穿透，PC 关机后看板仍显示最后一次快照。

```
PC 桥（本地，只出站）  --定时推送-->  GitHub 仓库  --直链-->  任意网络下的 Kindle
```

| | 局域网直连 | 远程快照 |
|---|---|---|
| 桥地址 | `http://192.168.x.x:8765` | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>`（**国内用镜像见下**，否则屏幕报「网络不通」） |
| 实时性 | 实时（3 分钟刷新） | 最近一次推送（默认每 10 分钟） |
| PC 要求 | 与 Kindle 同一网络 | 能上网即可，不需要公网 IP / 端口映射 / 穿透 |
| PC 关机 | 看板报错 | 继续显示最后一次快照 |

**一次性准备（约 3 分钟）**

1. 建一个 GitHub 空仓库，仓库名建议用一段随机字符串（如 `wb-board-xxxxxx`），Public 即可——免费账号的私有仓库无法匿名直链。
2. 开一个 fine-grained token：Repository access 只选这一个仓库，权限 `Contents: Read and write`。
3. 复制 `publish.ini.example` 为 `publish.ini`，填 `owner` / `repo` / `token`。
4. 验证并拿到地址：
```bash
python publish_snapshot.py --check            # 验证仓库与 token，打印 Kindle 该填的地址
python publish_snapshot.py --once --dry-run   # 取一次封面但不上传
python publish_snapshot.py --once             # 真推一次
python publish_snapshot.py --loop             # 持续推送（默认每 600 秒 / 10 分钟）
```
5. Kindle 端「设置桥地址」填下面两类之一（插件会自动拼上 `/cover_dark.png` 或 `/cover_light.png`（按主题）以及 `/status.json`，**无需手动加文件名**）：

   - **境外 / 能直连 GitHub 的用户**：`https://raw.githubusercontent.com/<owner>/<repo>/<branch>`
   - **中国大陆用户（推荐，否则屏幕报「网络不通」）**：`raw.githubusercontent.com` 在国内常被墙 / 超时，直连拉不到图，改用国内可直连的镜像：

     | 镜像 | Kindle 该填的桥地址 |
     |---|---|
     | **jsDelivr**（推荐，CDN 稳定） | `https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>` |
     | **ghproxy.net**（备用，更新更即时） | `https://ghproxy.net/https://raw.githubusercontent.com/<owner>/<repo>/<branch>` |

     > ⚠️ 镜像地址格式：jsDelivr 用的是 `@分支`（不是 `/分支`）。镜像对文件有**数分钟缓存**，所以远程刷新会比 10 分钟间隔再慢一点点，属正常；ghproxy 不缓存、更即时但依赖第三方可用性。
     >
     > 例：本项目的演示中继仓库若叫 `wb-board-xxxxxx`、分支 `main`，jsDelivr 地址即 `https://cdn.jsdelivr.net/gh/<owner>/wb-board-xxxxxx@main`。

**仓库不会膨胀（默认自动处理）**

`publish.ini` 的 `history = single`（默认）会走 Git Database API：每次推送用「只含这两个文件的 tree」建一个 **无父 commit**，再强制把分支指过去。结果：

- 历史长度**恒定 1 个 commit**，旧对象不可达后由 GitHub 回收 → 体积恒定，**永远不用手动清理**。
- 内容没变化时不产生 commit。
- 公开的 raw 直链**始终不变**，Kindle 端不受影响。

想保留完整历史才改 `history = append`（那时默认 600 秒间隔下约 144 commit/天，需要定期手动清）。

**注意**

- 远程模式走 `https`，要求 KOReader 自带 `ssl.https`（lua-sec）。绝大多数版本都有；万一没有，看板报错页会显示 `https 支持: 不可用 (缺 ssl.https 模块)`。
- `interval` 默认 600 秒（10 分钟）即可；`history = single` 下推送频率只影响 API 用量，不再影响仓库体积。
- 想常驻推送就双击 `publish_snapshot.vbs`（后台静默跑 `--loop`）；日志在 `publish.log`（由脚本自己写，因为 `pythonw` 没有控制台）。
- 远程看到的是**快照**不是实时画面；PC 关机后保留最后一次推送的内容。
- `publish.ini` 的 `width` / `height` = **推送到 GitHub 的封面尺寸**（远程模式是固定一张图，无法同时适配多机型）。**必须设成你主要看板的那台设备自身的屏幕分辨率**，否则该设备只会显示这张大图的「中心一块」（被裁切），看不到完整看板。常见机型取值见下方「远程模式该怎么填 width/height」。

### 远程模式该怎么填 width / height（按机型）

远程模式推到 GitHub 的是一张**固定尺寸**的图，插件原样 1:1 显示（不会自动缩放适配）。所以这张图的尺寸必须和你看板的设备屏幕一致，才能完整铺满、不裁切。

| 设备 | width | height |
|---|---|---|
| Kindle 3 / Keyboard / Kindle 4 / Touch（600×800 屏） | 600 | 800 |
| Kindle Paperwhite 1 / 2（758×1024 屏） | 758 | 1024 |
| Kindle Paperwhite 3 / 4 / 5、Voyage、Oasis（高清屏） | 1072 | 1448 |

- **不确定本机分辨率？** 进插件菜单触发一次看板，报错 / 信息页会打印 `screen: WxH`，那就是设备实际分辨率。
- **只用一台设备**：把 `width` / `height` 填成它的分辨率，远程快照完美铺满。
- **多台设备混用**：远程模式一份图只能喂一个分辨率——`ini` 填哪台，哪台完美，其余的会看到「中心被裁切的一块」。要么为常用那台填、偶尔切设备时改 `ini` 重推；要么**改用局域网模式**（插件自动按各设备尺寸实时渲染，天然不裁切）。

### 开机自启（重启后远程看板自动恢复）

远程模式要长期稳定，关键不是「手动起一次」，而是**重启电脑后无需任何操作就能自动续上**。已实测：按下面两步配置后，Windows 重启后约 1 分钟内桥与发布器自动拉起，Kindle 端看板自动恢复，无需人工干预。

1. **桥自启**：把 `workbuddy_bridge.vbs` 的快捷方式放进「启动」文件夹（`Win+R` → 运行 `shell:startup`）。登录后它会自动找到 Python、释放被占的 8765 端口、静默拉起桥，并用 `ServerXMLHTTP` 做健康检查。
   - ⚠️ 桥必须在**用户的交互登录会话**里跑——它要读 `~/.workbuddy/workbuddy.db` 才能拿到「空间-任务名」；在 SYSTEM / 无桌面会话下起，会读不到库而把任务名降级成「对话 / 上下文压缩」这类浏览器操作名。所以走「登录后自启」即可，别改成系统级服务。
2. **发布器自启**：把 `publish_snapshot.vbs` 的快捷方式也放进「启动」文件夹。它后台静默跑 `publish_snapshot.py --loop`，按 `interval` 持续把封面推到 GitHub 快照仓库。

> 两者都进启动文件夹后，整条链路（桥渲染 → 发布器推送 → Kindle 拉快照（raw 或镜像））在每次开机后自动闭环，正是「电脑重启也能刷得出来」的状态。

- 仓库是 Public 的：URL 只有知道的人才能访问，但**任务名和积分余额会出现在那张 PNG 上**。介意就把仓库名设得足够随机，或在 `publish.ini` 里设 `push_status = false` 少推一份 JSON。

## 常见问题

**Q：为什么锁屏 / 看板图一直不更新？**
A：先看电脑端 `bridge.log` 里有没有 `REQ from <Kindle IP>`。没有说明是 WiFi / 热点不通（Kindle 禁 ICMP，`ping` 不通是正常的）；有则说明链路通，问题在渲染侧。

**Q：时间戳冻在旧时间？**
A：常驻看板每 3 分钟主动重新拉图，时间戳（`SYNC <时间>`）会跟着变；若不变，多半是桥没收到请求（见上）。

**Q：Kindle 上点不动 / 只能重启？**
A：旧版曾因设备休眠吞掉触摸导致，现已在常驻期间暂停自动待机解决。若仍有偶发卡顿：每次自动刷新都会在 Kindle 主线程同步拉取封面图（KOReader 单线程限制），桥不可达时会阻塞数秒。新版本在下载前先做一次 2 秒 TCP 可达性探测——桥没响应就直接保留上一张图并拉长退避（60 秒），不再每 20 秒冻结一次；PC 端桥恢复后下次刷新自动续上。

**Q：Kindle 的 koreader 目录里堆了一堆 `wb_cover_*.png` 失效封面，怎么清？**
A：每次刷新都会生成唯一命名的封面缓存（`KOReader` 按路径缓存解码图，不能复用文件名），所以正常情况下只保留当前这张、删掉上一张；但**插件重载 / 崩溃后 `_last_cover` 指针丢失，旧的 EXPIRED 封面就会永久残留**。新版本会在**插件启动、唤醒、以及每次刷新开始前自动清理**——只保留屏幕上的那张和刚被替换掉的那张（`ImageWidget` 解码是惰性的，删太早会导致刷新失败），其余连同 `.tmp` 半成品一并删除；重启后指针为空时按修改时间保留最新一张。也可手动清理：菜单 `WorkBuddy Monitor → 清理看板缓存 (删除失效封面)`，或绑定手势 `WorkBuddy 清理看板缓存`，会提示删除了几个文件。

**Q：积分数值 / SYNC 时间不刷新，一直停在老数字？**
A：先分清是哪一端的问题。在 PC 上访问 `http://127.0.0.1:8765/status.json`，若 `credits.remaining` 和 `updatedAt` 都是新鲜的，说明桥和抓取都正常，问题在 Kindle 显示端。新版本已修掉一个会导致「画面卡在旧积分」的缺陷：自动清理曾把**正在被解码的封面**删掉（`ImageWidget` 惰性/异步解码，文件被删会导致换图失败），于是新图下载成功却显示不出来。现在**下载成功后不删任何图**，清理推迟到下一轮刷新开头执行，并额外保护 `_prev_cover`。若更新后仍不刷新，请在 Kindle 上完全退出并重启 KOReader（插件需重载才会带上新逻辑），并确认插件目录下的 `main.lua` 已被新文件覆盖。

**Q：封面显示 EXPIRED / 报警条？**
A：Cookie 过期了，按上面「登录失效了怎么办」刷新 `cookies.txt` 即可。

**Q：我用按键机（Kindle 3 这类没触屏），怎么退出看板？分辨率要怎么设？**
A：退出——进看板后按**任意物理键**即可：机身翻页键、5-way 方向键、5-way 中心、返回键都行，无需手势（触屏机的 tap / swipe / hold 同样有效）。
分辨率——**局域网模式下完全不用设**：插件会把设备自身屏幕尺寸带给桥，桥按该尺寸实时渲染，K3 自动出 600×800、高清机自动出自己的分辨率，各看各的都清晰、不裁切。只有**远程模式**推到 GitHub 的是一张固定尺寸的图，尺寸由你电脑端 `publish.ini` 的 `width` / `height` 决定（例子默认 `1072×1448`，适配 Paperwhite 这类高清机）：若 `ini` 填的是高清机的 `1072×1448`，K3 看远程快照只会显示这张大图正中的 `600×800` 一块（被裁切），看不到完整看板；反之亦然。所以请按上面「远程模式该怎么填 width/height」一节，把 `ini` 设成你主要看板的那台设备的分辨率。

## License

[MIT](LICENSE) © RC-APC
