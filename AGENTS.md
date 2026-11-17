# wenxinyiyan

本仓库是 WorkBuddy 提示词优化服务及 Windows 快捷键客户端。项目名不表示接入百度模型。

- 部署或迁移任务先读 `DEPLOY.md`，不要根据旧抓包推测运行配置。
- 项目可位于任意目录；代码使用脚本相对路径，不添加设备专属绝对路径。
- 服务端首次扫码、GitHub 授权、SSH 密钥授权由本人完成，不导出或提交账号登录凭据。
- `.wenxinyiyan-api-key`、`.env`、`desktop/settings.json`、`data/`、`migration-backup/`、抓包和日志不入 Git。
- 提交前运行 `python deployment/audit-source.py` 与有意义的相关测试。
- Python 检查：`python -m unittest desktop.test_agent test_optimizer_service test_workbuddy_optimizer`。
- AHK 解析检查：`desktop/runtime/AutoHotkey64.exe /ErrorStdOut=UTF-8 desktop/test_result_format.ahk`（Windows）。
- `/ready` 成功仅表示发现通信配置；实际登录可用性必须通过真实 `/optimize` 调用确认。
- 保留已有登录数据、密钥和无关容器配置；只管理本项目的 `wenxinyiyan` 容器。
- 不自动升级上游程序、不重复提交失败的模型请求、不使用永久管理员权限维持快捷键。
