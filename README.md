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

## 架构

```
 WorkBuddy 客户端/账号
        │ cookies
        ▼
  ┌─────────────────────┐
  │  PC 桥  wb-bridge.py │  监听 0.0.0.0:8765（仅标准库）
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
│   └── config.txt                #   第1行填桥地址，可选 theme=dark|light
├── wb-bridge.py                  # 电脑端桥（HTTP 服务，仅标准库）
├── cover_gen.py                  # PNG 渲染（Pillow）
├── fetch_credits.py             # 抓 WorkBuddy 实时积分（需 cookies.txt）
├── wb_sessions.py                # 读 WorkBuddy 本地会话库
├── parse_usage.py / scan_tasks.py# 其它数据源
├── deploy_to_kindle.py           # 部署插件到 Kindle（delete-first + 校验）
├── bridge_watchdog.bat          # 看门狗：端口没监听就拉起桥
├── _smoke_lua.py                 # 插件冒烟测试（lupa 真加载）
├── credits.example.json         # 静态积分模板
├── tasks.example.json           # 静态任务模板
└── README.md
```

## 安装

### 1. 电脑端桥（Windows / macOS / Linux，Python 3.8+，无需 pip）

```bash
cd workbuddy-koreader-monitor
python wb-bridge.py          # 监听 0.0.0.0:8765
```

- 默认读 `credits.json` / `tasks.json`（用 `credits.example.json` / `tasks.example.json` 复制改名即可）。
- 进阶：放一个 `cookies.txt`（WorkBuddy 网页登录后的 Cookie），桥会自动抓**实时积分**；Cookie 失效时自动回退静态数据。
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
http://192.168.137.1:8765     # 电脑开热点时
http://192.168.1.20:8765      # 同路由器时，填 PC 的 LAN IP
```

### 4. 绑定手势（可选但推荐）

KOReader：`设置 → 手势 → 添加手势 → 画一个手势 → 动作列表`里选：
- **WorkBuddy 常驻看板**（再触发一次即退出，相当于开关）
- **WorkBuddy 设置休眠壁纸**
- **WorkBuddy 退出常驻**

### 5. 锁屏封面（可选）

插件菜单「锁屏封面文件 → 查看位置与说明」会显示 `wb_ss/cover.png` 的绝对路径。
在 KOReader：`设置 → 屏幕 → 锁屏类型 = 随机图片`，`锁屏图片文件夹 =` 上面的 `wb_ss` 文件夹。
点过「设置休眠壁纸」后，看板每次刷新都会把最新一张复制进去，锁屏即自动更新。

## 开机自启（电脑端桥）

- **登录时**：Startup 里的 `workbuddy_bridge.vbs` 拉起 `bridge_watchdog.bat`（隐藏窗口，不弹黑框）。
- **兜底**：Windows 计划任务 `WB_Bridge_Watchdog` 每 **5 分钟**检查 8765 端口，没监听就重启桥；崩溃 / 重启后自愈。
- ⚠️ 当前用的是**交互登录令牌**（InteractiveToken），即**用户登录之后**桥才会起来（≤5 分钟），不是登录前的系统级服务。若要「开机即启（含锁屏前）」，把计划任务改成 **SYSTEM 账户 + 启动触发器**即可。

## 隐私与凭据

以下文件含凭据 / 个人数据，**已写入 `.gitignore`，绝不会进仓库**：

`cookies.txt` · `config.js` · `wb_account.json` · `credits_cache.json` · `plans_usage.html`

桥默认只监听局域网；可选 `WB_TOKEN` 做简单 Bearer 鉴权。

## 常见问题

**Q：为什么锁屏 / 看板图一直不更新？**
A：先看电脑端 `bridge.log` 里有没有 `REQ from <Kindle IP>`。没有说明是 WiFi / 热点不通（Kindle 禁 ICMP，`ping` 不通是正常的）；有则说明链路通，问题在渲染侧。

**Q：时间戳冻在旧时间？**
A：常驻看板每 3 分钟主动重新拉图，时间戳（`SYNC <时间>`）会跟着变；若不变，多半是桥没收到请求（见上）。

**Q：Kindle 上点不动 / 只能重启？**
A：旧版曾因设备休眠吞掉触摸导致，现已在常驻期间暂停自动待机解决。

## License

[MIT](LICENSE) © RC-APC
