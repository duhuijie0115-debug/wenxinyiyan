# wenxinyiyan 协议研究工具

根目录的 `*capture*`、`*inspector*`、`replay-local.js`、`inspect_asar.py`、`parse_capture.py` 等是本项目自有研究源码，保留在 Git 中供协议变更时参考。
它们不是日常运行或部署步骤。不得在正常自动维护中自动启用调试端口、抓取票据或导出 Token。

`Start-WorkBuddyCapture.ps1` 使用 `-Executable` 指定本人安装的 WorkBuddy 路径，其他诊断工具可通过 `WENXINYIYAN_ROOT` 与 `WORKBUDDY_INSTALL` 指定目录。
注入式表达式在 WorkBuddy 进程上下文执行，必须自行确认目标版本、端口和路径后才使用；历史重放端口不自动适配。
`capture-hook.cjs` 默认输出本脚本旁的 `capture/traffic.jsonl`，尽管进行脱敏，仍应视为私有数据。
抓包产物、解包得到的第三方源码/网页、账号登录文件不进入版本控制。
应用稳定运行只需要 `config/request-template.json`，不需要 `capture/` 或 `inspection/`。

历史协议结论见 `WorkBuddy-API分析.md`。其中曾引用的本机抓包验证文件仅原设备保留，仓库测试使用 `tests/fixtures/` 中的固定无账号样例。
