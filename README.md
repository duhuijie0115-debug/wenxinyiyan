# wenxinyiyan

源码仓库：https://github.com/duhuijie0115-debug/wenxinyiyan（私有）。

Windows 全局快捷键 + FastAPI 提示词优化服务。后端使用已登录的 **WorkBuddy**，项目名称不表示接入百度文心一言。

选中文字按 **Ctrl+Alt+O**，后台通过 NAS API 优化；选区仍保持时自动替换，同时把结果留在剪贴板。
期间继续操作会取消自动替换，可用 Ctrl+V 或 Ctrl+Alt+P 粘贴结果。

## 部署入口

将 [DEPLOY.md](DEPLOY.md) 发送给另一台设备的 agent，按其中流程部署。
该文件覆盖 Linux x86_64/NAS 服务端和 Windows x64 客户端；不能仅复制一个 Python 文件。
服务端首次扫码和 SSH 密钥授权需要本人完成，现有设备登录态、密钥均不包含在仓库内。

## 源码结构

| 路径 | 用途 |
| --- | --- |
| `workbuddy_optimizer.py` | 请求模板填充、requests 调用、SSE 完整性检查 |
| `workbuddy_transport.py` | Windows 命名管道 / Linux Unix socket 双向 HMAC 通信 |
| `optimizer_service.py` | FastAPI、密钥保护、输入校验、并发限制 |
| `config/request-template.json` | 脱敏的增强提示词请求模板；运行必需 |
| `desktop/optimizer.ahk`、`result_format.ahk` | 快捷键、选区保护、剪贴板交付、结果解析 |
| `desktop/agent.py` | 后台请求、进程守护、登录桌面辅助、日志与残留清理 |
| `deployment/` | 镜像、Compose、初始化、验证、Windows 安装脚本、SSH 桌面中继 |
| `test_*.py`、`desktop/test_*.py`、`tests/fixtures/` | 不依赖账号的自动化测试 |
| 根目录抓包/inspector 脚本 | 历史协议研究工具，非部署依赖；手动使用说明见 `RESEARCH.md` |

## 验证

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest desktop.test_agent test_optimizer_service test_workbuddy_optimizer
desktop\runtime\AutoHotkey64.exe /ErrorStdOut=UTF-8 desktop\test_result_format.ahk
```

AHK 测试需先按部署文件安装官方便携运行时。真实 NAS 验证（使用模型额度）：

```sh
python3 deployment/verify-service.py --url http://NAS_LAN_IP:18080 --optimize
```

`/health` 只证明 API 存活；`/ready` 只证明发现本机通信配置；只有真实优化成功才能证明登录和模型可用。
失败请求不会自动重放。上游登录失效需要重新扫码；上游内部协议变更可能需要维护，不承诺永久全自动。

运行数据、账号文件、原始抓包、安装包和本机专属配置均由 `.gitignore` 排除。仓库包含全部自有运行源码、部署脚本、测试及必要的配置示例；官方程序从校验过的下载地址获取。
