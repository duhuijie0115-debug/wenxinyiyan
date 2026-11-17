"""Bridge WorkBuddy's captured enhancement API using the existing login.

    from workbuddy_optimizer import optimize_prompt
    print(optimize_prompt("帮我写个贪吃蛇代码"))

Uses WorkBuddy's authenticated local request channel by default. An explicit
WORKBUDDY_AUTHORIZATION enables direct cloud requests instead.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import re
import sys
import uuid

import requests
from workbuddy_transport import WbipcAdapter, WbipcError

ROOT = Path(__file__).resolve().parent
URL = "https://www.workbuddy.cn/v2/chat/completions"
TEMPLATE = ROOT / "config" / "request-template.json"


class OptimizationError(RuntimeError):
    """An actionable API, authentication or stream error, without credentials."""


def _login_headers() -> dict[str, str]:
    override = os.environ.get("WORKBUDDY_AUTHORIZATION", "").strip()
    if override:
        headers = {"authorization": override}
        if user_id := os.environ.get("WORKBUDDY_USER_ID", "").strip():
            headers["x-user-id"] = user_id
        return headers

    return {}


def _request_parts(original_text: str) -> tuple[dict, dict]:
    try:
        captured = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        payload = deepcopy(captured["body"])
        user_message = next(m for m in payload["messages"] if m["role"] == "user")
        content = user_message["content"]
        if isinstance(content, list):
            part = next(p for p in content if p.get("type") == "text")
            template = part["text"]
        else:
            part = None
            template = content
        # Match fixed delimiters, not the previous user's text. A callable
        # replacement preserves literal backslashes and regex-looking input.
        enhanced_input, count = re.subn(
            r"(USER INPUT:[ \t]*\r?\n)[\s\S]*?(\r?\n[ \t]*TASK:)",
            lambda match: match[1] + "    " + original_text + "\n    " + match[2],
            template, count=1,
        )
        if count != 1:
            raise ValueError("Missing prompt delimiters")
        if part is None:
            user_message["content"] = enhanced_input
        else:
            part["text"] = enhanced_input
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        raise OptimizationError(f"抓包模板无效或缺失：{TEMPLATE}") from None

    header_names = (
        "x-requested-with", "x-agent-purpose", "x-ide-type", "x-ide-name", "x-ide-version",
        "x-agent-intent", "x-agent-runtime", "x-client-version", "x-client-platform",
        "x-client-product", "x-agent-type", "x-domain", "x-product", "user-agent",
    )
    headers = {k: captured["headers"][k] for k in header_names if k in captured["headers"]}
    headers.update({"Content-Type": "application/json", "Content-Encoding": "gzip",
                    "Accept": "text/event-stream"})
    headers.update(_login_headers())
    message_id = uuid.uuid4().hex
    headers.update({"x-request-id": message_id, "x-conversation-message-id": message_id,
                    "x-conversation-request-id": uuid.uuid4().hex,
                    "x-conversation-id": str(uuid.uuid4())})
    return headers, payload


def _sse_events(response):
    data = []
    for raw in response.iter_lines():
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if line == "":
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
    if data:
        yield "\n".join(data)


def _read_completion(response) -> str:
    chunks = []
    completed = False
    for event in _sse_events(response):
        if event.strip() == "[DONE]":
            completed = True
            break
        try:
            frame = json.loads(event)
        except ValueError:
            raise OptimizationError("云端返回无效的 SSE JSON 数据。") from None
        if not isinstance(frame, dict) or frame.get("error"):
            raise OptimizationError("云端返回模型错误，未获得完整增强结果。")
        for choice in frame.get("choices", []):
            if choice.get("finish_reason") in ("error", "length", "content_filter"):
                raise OptimizationError("模型未正常完成输出，请稍后重试。")
            content = (choice.get("delta") or {}).get("content")
            if isinstance(content, str):
                chunks.append(content)
    if not completed:
        raise OptimizationError("SSE 提前断开，未收到 [DONE]，不返回可能截断的结果。")
    result = "".join(chunks).strip().strip('\"\'“”‘’').strip()
    if not result:
        raise OptimizationError("模型返回空文本。")
    return result


def optimize_prompt(original_text: str, *, timeout: float = 300) -> str:
    """Return enhanced text; raise OptimizationError on failure.

    Uses WorkBuddy's current account and quota. Default mode requires a running,
    logged-in WorkBuddy, but no UI actions, debug port or local model sidecar.
    """
    if not isinstance(original_text, str) or not original_text.strip():
        raise OptimizationError("提示词不能为空。")
    headers, payload = _request_parts(original_text)
    raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    direct = bool(os.environ.get("WORKBUDDY_AUTHORIZATION", "").strip())
    body = gzip.compress(raw_body) if direct else raw_body
    try:
        with requests.Session() as session:
            url = URL
            if not direct:
                session.mount("wbipc://", WbipcAdapter())
                url = "wbipc://workbuddy/v2/chat/completions"
                headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            # Use system/environment proxy policy; retain normal TLS verification.
            with session.post(url, headers=headers, data=body, stream=True,
                              timeout=(15, timeout), allow_redirects=False) as response:
                if response.status_code in (401, 403):
                    raise OptimizationError(f"鉴权失效或权限不足（HTTP {response.status_code}）；请在 WorkBuddy 重新登录。")
                if response.status_code == 429:
                    raise OptimizationError("WorkBuddy 限流或排队（HTTP 429），请稍后重试。")
                if response.status_code != 200:
                    raise OptimizationError(f"WorkBuddy 请求失败（HTTP {response.status_code}）。")
                if "text/event-stream" not in response.headers.get("Content-Type", "").lower():
                    raise OptimizationError("云端响应格式变化：预期 SSE。")
                return _read_completion(response)
    except requests.Timeout:
        raise OptimizationError("WorkBuddy 请求超时。") from None
    except WbipcError as error:
        raise OptimizationError(str(error)) from None
    except requests.RequestException:
        raise OptimizationError("网络连接失败，请检查网络或代理配置。") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 WorkBuddy 当前登录态增强提示词")
    parser.add_argument("text", nargs="?", help="原始提示词；省略时读取 stdin")
    parser.add_argument("--output", type=Path, help="将结果写入 UTF-8 文本文件")
    args = parser.parse_args()
    try:
        result = optimize_prompt(args.text if args.text is not None else sys.stdin.read())
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result)
        return 0
    except OptimizationError as error:
        print(f"优化失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
