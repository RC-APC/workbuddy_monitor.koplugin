# WorkBuddy KOReader Monitor · 安装指引（给 WorkBuddy 用）

本指引供 WorkBuddy 在带用户安装「WorkBuddy KOReader Monitor」插件时逐步执行。
插件作用：把电脑端 WorkBuddy 的状态（积分、即将到期点数、在跑任务）每 3 分钟渲染成一张
赛博朋克封面图，经局域网/远程推到 Kindle 墨水屏，变成一块常驻 AI 状态看板。

---

## 0. 前置条件

- 一台装了 **KOReader** 的 Kindle（或任何跑 KOReader 的墨水屏设备）。
- 一台电脑（Windows / macOS / Linux，Python 3.8+，仅需 `pillow` 一个第三方依赖）。
- 二者在**同一 WiFi**（局域网快速模式），或用户愿意做远程快照推送（跨网络，推荐但稍复杂）。
- 已拿到本仓库（`workbuddy_monitor.koplugin/` 目录 + `wb-bridge.py` 等脚本）。

> 关键心智模型：**两半，各自装一次**。
> 1. 电脑端「桥」`wb-bridge.py` —— 渲染封面、监听 `0.0.0.0:8765`。
> 2. Kindle 端「插件」`workbuddy_monitor.koplugin/` —— 拉图、铺满墨水屏。
> 两者通过 `http://<电脑IP>:8765` 通信。

---

## 1. 电脑端桥（先做，5 分钟）

```bash
cd /path/to/workbuddy-koreader-monitor
pip install pillow            # 唯一第三方依赖
python wb-bridge.py           # 监听 0.0.0.0:8765
```

**Windows 最简**：直接双击 `workbuddy_bridge.vbs` —— 它会自动找本机 Python、释放被占用的
8765 端口、静默拉起桥，并做健康检查后弹确认框。

- 桥默认读 `credits.json` / `tasks.json`（用仓库里的 `credits.example.json` /
  `tasks.example.json` 复制改名即可）。没有也行，会回退静态占位。
- **实时积分**（可选）：在目录放一个 `cookies.txt`（WorkBuddy 网页登录后的 Cookie），
  桥会自动抓实时积分与今日已用；Cookie 失效时自动回退静态数据并报警。格式见
  `cookies.txt.example`（取 Cookie 方法见末尾「登录失效」一节）。

✅ 验证桥起来了：浏览器开 `http://127.0.0.1:8765/cover.png` 能看到一张图即成功。

---

## 2. Kindle 端插件（USB 拷入）

把 Kindle 用 USB 挂到电脑：
- **Windows**：通常是一个盘符，如 `F:/`（也可能 `E:/`、`G:/`）。
- **macOS / Linux**：自动挂载到 `/Volumes/Kindle` 或 `/media/$USER/Kindle`。

用本 skill 自带的参数化部署脚本（处理 KOReader 文件锁，见「坑 1」）：

```bash
# Windows（假设 Kindle 在 F:，仓库在本目录）
python scripts/deploy_kindle.py \
    --src ./workbuddy_monitor.koplugin \
    --dst F:/koreader/plugins/workbuddy_monitor.koplugin

# macOS / Linux
python scripts/deploy_kindle.py \
    --src ./workbuddy_monitor.koplugin \
    --dst /Volumes/Kindle/koreader/plugins/workbuddy_monitor.koplugin
```

脚本会等待 KOReader 释放文件锁、写入并**逐字节校验**。提示 `DEPLOYED AND VERIFIED`
即成功。

⚠️ **装完必须重启一次 KOReader**（菜单 → 退出 KOReader 再进，或直接重启设备）。
插件才会出现在 KOReader 的「插件」菜单里。

> 不想用脚本也可以手动：把 `workbuddy_monitor.koplugin/` 整个文件夹复制到
> `<Kindle>/koreader/plugins/` 下。但**不要在 KOReader 运行时覆盖单个文件**
> （会被锁，见坑 1）——先退出 KOReader 再拷最稳。

---

## 3. 配置桥地址（让插件找到电脑）

编辑 Kindle 上的 `workbuddy_monitor.koplugin/config.txt` 第 1 行，填电脑桥地址：

```
http://192.168.137.1:8765     # 电脑开热点，Kindle 连热点时
http://192.168.1.20:8765      # 同路由器时，填 PC 的 LAN IP
```

两种填法二选一：
- **改 `config.txt` 后重新部署**（见第 2 步脚本，会一并覆盖）。
- 或在 Kindle 上 KOReader 插件菜单里直接「设置桥地址」（菜单改过的地址优先级更高）。

查电脑 LAN IP：
- Windows：`ipconfig` 看「WLAN 适配器」的 IPv4。
- macOS / Linux：`ifconfig` 或 `ip addr`。

✅ 验证：Kindle 上打开插件「WorkBuddy 常驻看板」，墨水屏出现积分环 + 任务条即通。
每 3 分钟自动刷新。

---

## 4. 可选增强

- **绑定手势**（推荐）：KOReader `设置 → 手势 → 添加手势`，动作选
  「WorkBuddy 常驻看板」（再触发一次即退出，相当于开关）。
- **锁屏封面**：插件菜单「锁屏封面文件 → 查看位置」会给出 `wb_ss/cover.png` 路径；
  在 KOReader `设置 → 屏幕 → 锁屏类型 = 随机图片`，`锁屏图片文件夹 =` 填那个 `wb_ss`
  文件夹。点过「设置休眠壁纸」后锁屏自动更新。

---

## 5. 远程模式（跨网络，推荐长期用）

局域网模式要求 Kindle 和电脑同 WiFi。要让**出门也能看**，用远程快照：电脑端把封面
推到一个只有你自己知道的 GitHub 空仓库（匿名直链），Kindle 拉那个 URL。

准备（一次性，约 3 分钟，详见 `publish.ini.example`）：
1. GitHub 新建一个空仓库（仓库名用随机串如 `wb-board-xxxxxx`，选 Public，免费私有仓库
   无法匿名直链）。
2. `Settings → Developer settings → Personal access tokens → Fine-grained tokens`
   生成 token：仅勾该仓库，`Contents: Read and write`。
3. 复制 `publish.ini.example` 为 `publish.ini`，填 `owner / repo / token`。
4. 跑 `python publish_snapshot.py --check` 验证，并打印 Kindle 该填的地址：
   `https://raw.githubusercontent.com/<owner>/<repo>/<branch>`。
5. Kindle 插件菜单「设置桥地址」填上面那行（注意：远程模式填的是**快照 URL**，不是
   `http://IP:8765`）。

远程模式看到的是「最近一次推送的快照」，不是实时画面；间隔默认 5 分钟（在 `publish.ini`
的 `interval`）。开机自启配置见仓库 README 的「远程模式」一节。

---

## 坑（务必记牢）

**坑 1 — KOReader 文件锁**：KOReader 运行时会锁住插件的 `main.lua` / `config.txt`。
直接 `cp -f` 或 `open("wb")` 覆盖会报 `Permission denied`，且 `cp -f` 可能**假成功只写
了一部分**。可靠做法是 **先删再写**（`rm dst; cp src dst`），脚本已封装好。
若一直 `TIMEOUT`，确认 KOReader 在运行，或先退出 KOReader 再部署。

**坑 2 — DHCP IP 会变**：同 WiFi 下电脑 IP 是动态的，重连 / 休眠唤醒 / 路由器重启后
可能变。变了对不上就黑屏。排查：`ipconfig` 查 WLAN 的 IPv4 重新填并重新部署。

**坑 3 — Cookie 过期**：`cookies.txt` 是会话凭证，几天到几十天过期。过期后桥**明确报警**
（Kindle 封面顶部反白条 `▲ 登录已失效`，`CREDITS` 徽标从 `LIVE` 变 `EXPIRED`）。
恢复：重新登录 workbuddy.cn → F12 复制新 `cookie:` 整行 → 替换 `cookies.txt` 第 1 行 →
双击 `workbuddy_bridge.vbs` 重启桥。

**坑 4 — 装完要重启 KOReader**：拷完插件不重启，菜单里看不到它。

**坑 5 — 多开桥**：桥用 `SO_REUSEADDR`，允许多进程同绑 8765。多次双击
`workbuddy_bridge.vbs` 会攒出多个桥，导致封面错乱。查 `netstat -ano | findstr :8765`
只应有 1 个 LISTEN；多了重启电脑清回 1 个。

---

## 登录失效时取 Cookie 的正确姿势

1. 浏览器登录 `workbuddy.cn`（退出再登或等会话续期）。
2. F12 → Network（网络）→ 刷新页面 → 点任意发往 `workbuddy.cn` 的请求 →
   Headers → Request Headers → 找到 `cookie:` 那一行 → **右键 → Copy value**（整串）。
3. 打开 `cookies.txt`，**只把第 1 行整行替换为新串**保存（`#` 注释行会被忽略）。
4. 双击 `workbuddy_bridge.vbs` 重启桥；报警条消失、`LIVE` 回来即恢复。

> 不要从「右键 → Copy as cURL」里摘 cookie——能用，但不如上面方法干净。桥只认
> `cookies.txt` 文件，不读环境变量。
