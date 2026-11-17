# WorkBuddy「增强提示词」API 抓取结果

2026-11-17；WorkBuddy 5.11.3 / CLI 2.176.0。

## 结果与验证范围

已动态记录一次按钮调用的本机 HTTP 请求及成功响应。修改输入文本后，在原后台进程内重放两次，均返回 HTTP 200、`success:true`。第二次重放完整捕获 gzip 解压后的云端 JSON 请求及 SSE 响应。

采用临时 Node inspector 和进程内 HTTP 记录器，没有安装 HTTPS 根证书，没有修改安装包。交付文件中的 Authorization、Cookie、用户标识和私有数据头已脱敏。

## 数据流与调用时机

```text
点击「增强提示词」
 → daemonClient.enhancePrompt({text, sessionId?})
 → 本机 RPC llm:enhancePrompt
 → 后台构造 systemPrompt 和 userPrompt
 → POST http://127.0.0.1:<动态端口>/api/v1/llm/completions
 → 模型服务选择 lite 对应的产品模型
 → POST https://www.workbuddy.cn/v2/chat/completions
 ← SSE：choices[].delta.content / reasoning_content / usage / [DONE]
 ← 本机 JSON：{text, success}
 → 前端替换输入框文本
```

增强本身不创建普通聊天任务。后台静态代码只使用前端传入的 `text`；本次没有观察到历史聊天消息加入请求。

## 本机接口

```http
POST http://127.0.0.1:63473/api/v1/llm/completions
Content-Type: application/json
Authorization: Bearer <进程临时凭据>
```

`63473` 只属于本次进程。之前进程使用 `55551`，不能写死端口。

```json
{
  "systemPrompt": "完整内置系统指令，见 capture/local-request.json",
  "userPrompt": "含 USER INPUT 和 TASK 的完整用户模板，见附件",
  "agentName": "enhance-prompt",
  "model": "lite"
}
```

| 字段 | 本次观察 | 必要性证据 |
|---|---|---|
| systemPrompt | 提示词工程专家指令；保持意图和语言，约 800 字符以内，只输出增强文本 | 按钮总是发送；未做删除实验 |
| userPrompt | 含原文的完整模板，不是裸原文 | 修改其中 USER INPUT 后已重放成功 |
| agentName | `enhance-prompt` | 按钮发送；未做删除实验 |
| model | `lite`，产品轻量模型别名 | 按钮发送；未做删除实验 |
| temperature / maxTokens / maxTurns | 通用客户端支持，但按钮未提供 | 当前增强路径可省略 |

原生请求还含 accept、x-request-id、user-agent、content-length、accept-encoding、host 等头。重放代码仅显式提供 Authorization 和 Content-Type，由运行时补充其他传输头；不能据此推断云端头部也可任意删除。

成功响应：

```json
{"text":"增强后的提示词","success":true}
```

测试原文为「请写一个 Python 脚本，将指定文件夹中的图片按拍摄日期重命名。测试标记 WB_OPT_20261117。」。两次重放分别返回 171、191 字符的增强文本，末次结果见 `capture/enhanced-prompt.txt`。

无鉴权访问本机服务，实测返回 HTTP 401：

```json
{"error":{"code":"AUTH_REQUIRED","message":"Authentication required"}}
```

后台 RPC 层失败还可能含 `success:false`、`text:""`、`code`、`error`。静态识别错误码有 `empty_input`、`sidecar_unavailable`、`llm_error`、`unknown`；不是云端错误结构保证。

## 云端接口

```http
POST https://www.workbuddy.cn/v2/chat/completions
Content-Type: application/json
Content-Encoding: gzip
Authorization: <现有登录鉴权，值已脱敏>
```

传输请求体使用 gzip 压缩。gzip 不是业务加密，HTTPS 提供传输加密。解压后字段如下；完整值见 `config/request-template.json`：

```json
{
  "model": "hy4flash-free",
  "messages": [
    {"role":"system","content":"内置系统指令"},
    {"role":"user","content":"完整用户模板，含 USER INPUT"}
  ],
  "tools": [
    {"type":"function","function":{"name":"SendMessage","parameters":"见完整请求"}},
    {"type":"function","function":{"name":"ExitPlanMode","parameters":"见完整请求"}}
  ],
  "stream": true,
  "stream_options": {"include_usage":true},
  "extra_vars": {
    "harnessMetadata":"{\"schemaVersion\":1,\"harnessVersion\":\"2.176.0\",\"agent\":{\"depth\":0}}",
    "initiator":"agent"
  },
  "cache_retention":"long",
  "reasoning_summary":"auto"
}
```

这是结构示意，说明性占位不可直接用于请求。工具定义由框架附带，不代表增强过程必须实际执行工具。`lite` 本次映射为请求模型 `hy4flash-free`，响应模型名为 `hy4-flash-free`；未来映射可能变化。

| 关键请求头 | 观察值或含义 |
|---|---|
| authorization | 云端登录鉴权，与本机随机 Bearer 不同 |
| x-agent-purpose | `enhance-prompt` |
| x-agent-type | `auxiliary` |
| x-agent-intent | `craft` |
| x-agent-runtime | `other` |
| x-client-product | `WorkBuddy` |
| x-domain / x-product | `www.workbuddy.cn` / `SaaS` |
| user-agent | `WorkBuddy/5.11.3 WorkBuddy/5.11.3 CLI/2.176.0` |
| x-user-id / x-private-data | 用户或私有数据，已脱敏；未推断内部算法 |
| x-conversation-id / x-conversation-message-id / x-conversation-request-id | 两次请求间变化 |
| x-request-id / traceparent / b3 / x-b3-* / x-trace-id | 两次请求间变化，属于请求与链路标识 |
| x-stainless-* | SDK 环境、版本、重试相关信息 |

未对云端字段做逐项删除验证，不能将「已观察到」当作「全部必须」或「全部可省略」。完整头列表见附件。

## SSE 响应

实测 HTTP 200、`Content-Type: text/event-stream`。末次捕获有 414 个 JSON 数据帧及结束标记 `data: [DONE]`。

```text
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"文本片段","reasoning_content":"..."},"finish_reason":""}]}

data: {"choices":[...],"usage":{...}}

data: [DONE]
```

按 SSE 事件读取，跳过 `[DONE]`，累加 `choices[].delta.content` 得到输出文本。`reasoning_content` 不应拼入增强文本；`usage` 是计量字段；本次 `finish_reason` 为 `stop`。

末次 usage：3710 输入 tokens、1160 输出 tokens、4870 总 tokens，响应 `credit:0`。这只是本次返回计量，不保证永久免费或没有额度、排队和限流。

## 鉴权和动态字段

- 本机凭据源码：`getGatewaySecret()` 生成 32 随机字节，再作 base64url 编码；进程内生成，通过子进程环境配置服务鉴权。重启后不能假设仍有效。
- 云端使用现有登录态；本轮没有验证令牌有效期、刷新流程或完整签发机制。
- 未观察到独立命名的请求签名头，但不足以证明服务没有其他校验。
- 不能把本机 Bearer 当成云端鉴权，也不要固定历史追踪 ID。

## 交付文件

- `capture/local-request.json`：真实按钮请求，已脱敏。
- `config/request-template.json`：末次云端请求头及解压后的 JSON。
- `capture/cloud-response-headers.json` / `cloud-response.sse`：响应头和完整 SSE。
- `capture/replay-request.json` / `replay-response.json`：修改文本后的重放。
- `capture/enhanced-prompt.txt`：末次增强结果。
- `capture/summary.json`：字段、模型、动态头和计量汇总。
- `capture/traffic.jsonl`：本轮记录器输出，含重复观察和调试失败记录。
- `parse_capture.py`：脱敏、解压结果整理及 SSE 解析脚本。

首次重放曾因记录器过早读取入站请求体产生 500；修正后两次重放成功。该 500 是抓取工具导致的，不作为服务正常错误行为证据。

临时调试端口仅绑定本机。任务结束时退出抓取模式并普通重启应用，撤销内存钩子和调试端口。启动脚本已去掉发行版不支持的 NODE_OPTIONS 预加载；需通过 inspector 附加记录器，不能只启动脚本就假定已完整抓取。
