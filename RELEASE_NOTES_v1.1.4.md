# WorkBuddy KOReader Monitor — 发布说明 v1.1.4

## 封面个性化

- 积分区右侧新增 Claude Code `/buddy` 风格 **ASCII 终端宠物**（20 款物种），按本地 WorkBuddy 账号 UID 确定性分配，每台设备稳定不重样。
- 页眉问候语支持自定义称呼：取自 `~/.workbuddy/USER.md` 的「WorkBuddy 对你的称呼」，没填就只显示随机祝福语，**绝不回退成 ID**。
- `publish.ini` 的 `display_name` / `user_id` 已退役，身份全自动来自本地账号。

## 稳定性

- 全链路 `pcall` 加固刷新 / 下载 / 退出路径，解决此前「卡死只能重启」的问题。

## 看板常驻体验

- 新增 `auto_exit_stale=0` 可彻底关闭「15 分钟无刷新自动退出看板」：之后看板只在你手动退出（菜单「✕ 退出常驻看板」或按翻页/返回键）时才关，刷新失败也只会停在最后一帧好图上、绝不自动锁屏。
- **修复 Kindle 固件级自动挂起（回退锁屏）**：此前即使把 KOReader「自动待机」设成 59 分钟，设备仍每隔约 15 分钟自动挂起回锁屏——因为那是 **Kindle 固件自己的 T1 待机定时器**，不在 KOReader 设置范围内（KOReader 在本机上并不去喂固件 T1 看门狗）。本版本在看板显示时通过 powerd 的 `lipc-set-prop com.lab126.powerd preventScreenSaver 1` 直接压住固件 T1，关闭看板时复位为 `0`。该机制与 KOReader 自带「保持活动状态（KeepAlive）」插件完全相同，因此**无需另行开启该插件**。

## 升级提示

1. 用本项目 `workbuddy_monitor.koplugin.zip` 覆盖 KOReader 插件目录。
2. **彻底退出 KOReader 再重新打开**（插件启动时才加载，不重启新逻辑不生效）。
3. 如设置了 `auto_exit_stale=0`，修改后同样需重启 KOReader。
4. 远程模式用户：在 PC 端 `publish.ini` 保持 `interval`（如 300 秒 = 5 分钟）即可。
