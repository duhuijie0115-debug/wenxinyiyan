# wenxinyiyan — Agent 完整部署入口

这是可直接交给另一台设备 agent 的部署任务说明。目标是部署完整的 WorkBuddy 提示词增强系统，包括 Linux/NAS 服务与 Windows 全局快捷键客户端。项目名为 **wenxinyiyan**，实际模型与登录仍来自 **WorkBuddy**，不要配置百度 API。

## 0. Agent 执行约束与输入

先通读本文件，再检查目标设备，不要把“文件存在”当成部署成功。所有命令从仓库根目录执行。
源码仓库：`https://github.com/duhuijie0115-debug/wenxinyiyan`（私有，需要该设备取得 GitHub 读取授权）。
若只收到这个文件，先确认该设备的 GitHub 授权，再执行 `git clone https://github.com/duhuijie0115-debug/wenxinyiyan.git`。
无权限时请用户授予仓库访问或提供源码压缩包；不能凭空生成缺失源文件，也不能复制其他设备的 GitHub Token。
本文件随源码仓库一起版本控制，README 提供入口。配置中的 LAN IP 和 SSH 别名必须按目标设备填写，不得照搬原设备值。

必须确认的输入：

- `SERVER_LAN_IP`：Linux/NAS 的实际局域网 IPv4 地址；默认端口 18080。
- `SERVER_ROOT`：服务端持久化项目目录，例如 `/vol2/docker/wenxinyiyan`。
- `SSH_ALIAS`：Windows 已配置的免密 SSH 别名，例如 `feiniu`；以只读 `ssh ALIAS hostname` 验证目标。
- `WINDOWS_ROOT`：客户端目录，例如 `F:\wenxinyiyan`。
- 同一 WorkBuddy 账号由用户首次扫码登录。不要读取/迁移其他设备的登录票据、私钥或密码。

只读检查优先，不覆盖无关配置。不删除已有 data、密钥、容器或启动项。若是旧版迁移，按第 6 节操作。
不得将 API 密钥、SSH 私钥、登录配置、原始抓包提交 Git 或打印到会话。 sudo 密码只由本人在终端输入。
如果源设备有自己的 AGENTS.md、sudo 终端包装器等规则，优先遵循，不使用保存密码的自动化。

## 1. 依赖和前置条件

服务端：Linux **x86_64/amd64**，Docker Engine 与 Compose v2，Python **3.11+**（初始化/验证用），SSH 服务，至少 4 GB 可用内存和 6 GB 可用磁盘。容器限额默认 4 GB/2 CPU。
ARM 设备不能直接运行当前固定的 x64 安装包；检测到 ARM 时停止并报告，不伪装部署成功。
运行 API 的主机必须可访问 `www.workbuddy.cn`；构建还需访问 `download.codebuddy.cn`、Debian 镜像、PyPI 镜像和基础镜像仓库。

Windows 客户端：Windows 10/11 x64、Python 3.11+、PowerShell **7+**、OpenSSH client，以及可用局域网连接。
快捷键运行时为官方 AutoHotkey **2.0.31** 便携版，由脚本下载且校验 SHA-256，无需系统安装或管理员权限。

服务端容器包含：WorkBuddy 官方 Linux 5.6.2.40046327、Xvfb、Openbox、Chromium、x11vnc、noVNC/websockify、Supervisor、Python、requests、FastAPI 和 uvicorn。
官方包地址和固定校验值位于 `deployment/prepare-server.py` 与 Dockerfile。
该官方 Linux 版本已验证支持本项目的 WBIPC 请求通道。不要自动换最新版后假定协议仍兼容。
容器内 GUI 程序以 app(uid1000) 运行，Supervisor 执行初始化；不需要 privileged、宿主 Docker socket 或额外内核权限。
Electron/Chromium 在这个独立容器内使用 `--no-sandbox`；浏览器仅用于 WorkBuddy 登录，不浏览无关内容。

## 2. Linux/NAS 服务端部署

确认 `hostname`、`uname -m`、`python3 --version`、`docker version`、`docker compose version`，检查目标目录及端口是否占用。
如果 Docker 需要 sudo，下列 Docker 命令通过本机既定的 sudo 流程运行，不修改 docker.sock 权限，不把用户加入额外权限组。

取得源码到 `SERVER_ROOT` 后：

```sh
cd /实际路径/wenxinyiyan
python3 deployment/prepare-server.py --bind-ip SERVER_LAN_IP
```

初始化将下载并校验约 410 MB 的官方包到 `deployment/downloads/WorkBuddy.deb`；创建 `.wenxinyiyan-api-key`、`.env`、`data/`。
重复执行保留已有配置/密钥/数据；若已有 `.env`，必须检查其中绑定 IP 是否匹配本机。
API 密钥文件不可为空。只将 **API 密钥**通过受保护方式复制给需要调用服务的客户端，不复制 WorkBuddy 登录目录。

```sh
# 使用本机 sudo 规范执行；只修正本项目新建文件的权限。
sudo chown 1000:1000 .wenxinyiyan-api-key data
sudo chmod 600 .wenxinyiyan-api-key
sudo chmod 700 data
sudo docker compose --env-file .env -f deployment/compose.yaml config --quiet
sudo docker compose --env-file .env -f deployment/compose.yaml up -d --build
sudo docker compose --env-file .env -f deployment/compose.yaml ps
```

容器名、Compose 项目名均为 `wenxinyiyan`；镜像 `wenxinyiyan:5.6.2`。
`data/` 挂载到 `/home/app`，保存 WorkBuddy 登录目录和稳定 machine-id；密钥只读挂载为 `/run/secrets/wenxinyiyan-api-key`。
API **只绑定 `.env` 中的 LAN IP**，桌面只绑定宿主 `127.0.0.1:16080`。不要开放桌面到 LAN/公网。
Compose `restart: unless-stopped` 与 Supervisor 提供服务恢复；确认 Docker 服务本身随系统启动。

`.env` 的配置：

| 变量 | 必填 / 默认 | 作用 |
| --- | --- | --- |
| `WENXINYIYAN_BIND_IP` | 必填 | 实际 LAN IP，不接受空值 |
| `WENXINYIYAN_API_PORT` | 18080 | 宿主 API 端口 |
| `WENXINYIYAN_DESKTOP_PORT` | 16080 | 宿主 localhost 桌面端口 |

应用环境变量：`OPTIMIZER_HOST`、`OPTIMIZER_PORT`、`OPTIMIZER_API_KEY_FILE` 在镜像内已有默认值。
`OPTIMIZER_API_KEY` 可替代密钥文件；若二者同时配置，以文件为准。监听非 localhost 必须配置非空密钥。
`WORKBUDDY_HOME` 默认当前用户 `~/.workbuddy`；通常无需改动。
显式 `WORKBUDDY_AUTHORIZATION`/`WORKBUDDY_USER_ID` 的直接云端模式未验证，不作为本部署路径，不需要配置。

## 3. 首次 WorkBuddy 登录

在 Windows 确认 `ssh SSH_ALIAS hostname` 成功。SSH 使用本人授权的密钥；首次 host key 必须按实际指纹确认，不能关闭 host key 检查。
服务端 SSH 用户需能运行 python3，并能访问服务端 `127.0.0.1:16080`。无需启用 SSH AllowTcpForwarding。

Windows 源码目录中执行：

```powershell
python deployment\desktop_tunnel.py --ssh-host SSH_ALIAS --remote-port 16080
```

打开 `http://127.0.0.1:16080/vnc.html?autoconnect=1&resize=scale`；显示的是服务端桌面。
由本人点击 WorkBuddy `Sign In`，在容器内 Chromium 中扫码；代理或网络异常应先修复网络，不绕过认证。
确认登录成功，再继续。中继运行期间保持终端，完成后 Ctrl+C 停止中继；容器与 API 不受影响。

验证服务：

```sh
python3 deployment/verify-service.py --url http://SERVER_LAN_IP:18080
python3 deployment/verify-service.py --url http://SERVER_LAN_IP:18080 --optimize
```

前者验证 `/health`、未授权请求 401 和 `/ready`；后者发起真实优化，**会使用账号模型额度**。
只有 `--optimize` 返回 PASS 才能确认完整调用可用。HTTP 502 登录错误需要重新扫码，不能以 `/ready` 200 宣称已登录。
随后只重启本项目容器再验证，确认挂载保留登录态：

```sh
sudo docker compose --env-file .env -f deployment/compose.yaml restart wenxinyiyan
# 等待 API 和 WorkBuddy 启动后再执行，不反复创建容器。
python3 deployment/verify-service.py --url http://SERVER_LAN_IP:18080 --optimize
```

## 4. Windows 快捷键客户端

将同一源码放在 `WINDOWS_ROOT`。通过 SSH/SCP 或其他受保护途径取得服务端 `.wenxinyiyan-api-key` 到本机，勿在聊天粘贴密钥。
PowerShell 7 执行：

```powershell
cd F:\wenxinyiyan # 按本机实际路径替换
pwsh -File deployment\setup-windows.ps1 `
  -ApiUrl 'http://SERVER_LAN_IP:18080' `
  -ApiKeyFile 'C:\受保护目录\wenxinyiyan-api-key' `
  -SshHost SSH_ALIAS
```

脚本创建 `.venv`、安装依赖、下载校验 AHK、设置密钥/临时文本目录 ACL、写入本机 `desktop/settings.json`、验证服务、创建当前用户 Startup 的 `wenxinyiyan.lnk` 并隐藏启动。
无需修改机器启动项、管理员权限或文件关联。`-NoStart` 可仅完成配置与验证。
源码路径可不同，不依赖 F 盘；脚本根据自身位置计算目录。不要移动已启动的目录；移动前退出工具，移动后重新执行 `desktop/install.ps1` 更新快捷方式。

本机设置（`desktop/settings.example.json` 为示例，实际 `settings.json` 不提交）：

| 项 | 含义 |
| --- | --- |
| `api_url` | 含协议和端口的实际服务地址 |
| `api_key_file` | 相对仓库根的密钥路径，默认 `.wenxinyiyan-api-key` |
| `ssh_host` | 桌面登录辅助所用 SSH 别名 |
| `desktop_local_port` / `desktop_remote_port` | 中继本机端口 / NAS localhost 端口 |
| `automatic_login_assistance` | 是否在真实调用发现登录失效时打开登录桌面 |

实测标准可编辑文本框：选中“帮我整理会议纪要”，按 Ctrl+Alt+O，等待数秒，检查原选区被替换，并检查 Ctrl+V 可粘贴完整结果。
再做一次请求，期间切换窗口/输入，确认不误替换，结果留在剪贴板，Ctrl+Alt+P 可主动粘贴。
工具普通权限运行；管理员程序、某些自绘/只读输入控件不保证自动替换。
若 agent 的 UI 工具受限，必须报告未完成的交互验证，不把单元测试当成真实快捷键验证。

## 5. 维护、停机与验收

- WorkBuddy 自行维护登录态，容器重启保留用户目录；失效时自动辅助打开桌面，但**扫码不可全自动**。
- Windows 代理进程守护 AHK，周期检查通信配置，临时文本 10 分钟后清理，日志不写提示词/结果/密钥且轮转。
- API 密钥 401 与 WorkBuddy 登录失效不同：检查两端密钥一致，勿重新抓包导出 Token。
- 错误不自动重放模型请求；自动升级 WorkBuddy 或镜像可能改变内部协议，必须测试后再升级。
- Windows 取消自启：`pwsh -File desktop/install.ps1 -Uninstall`，随后从托盘退出。
- 服务停止：`sudo docker compose --env-file .env -f deployment/compose.yaml stop`；恢复用 `up -d`。不要 `down -v` 或删除 data。
- 备份本项目 `data/`、`.env`、密钥到受保护存储；不要上传到源码仓库。日志可能含账号信息，不公开原始日志。

最终报告至少包含：设备/目录、容器状态、端口绑定、真实优化结果是否成功、重启后是否保留登录、Windows 自启与快捷键是否实测、任何需要本人操作的步骤。

## 6. 从旧名称迁移

旧设备使用 `/vol2/docker/workbuddy-optimizer`、容器 `workbuddy-optimizer`、旧 API 文件 `optimizer-api-key`，Windows 使用 `F:\优化提示词工具` 与 `.optimizer-api-key`。
先只读检查实际路径、挂载和目标不存在；记录密钥文件位置但不要打印其内容。
迁移会短暂停机，先说明影响。停止旧容器但保留其恢复路径，移动已核实的项目根到 `wenxinyiyan`。
将现有数据目录挂载到新服务、复制旧密钥为 `.wenxinyiyan-api-key`，不生成新密钥、不覆盖登录数据。
安装仓库中的 Compose 与配置，启动新容器，真实验证后删除旧的停止容器（不删挂载数据）或保留用于回退；不要同时启动旧/新容器争抢端口。
Windows 先退出仅属于本项目的进程，再移动项目目录并更新 Startup 链接。本仓库安装脚本会移除旧名称启动链接。
`.venv` 内的入口脚本可能有旧绝对路径，优先重建 venv 或始终用 `.venv/Scripts/python.exe -m ...`。
