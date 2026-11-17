"""requests adapter for WorkBuddy's existing authenticated wb.request pipe.

Uses the application's normal mutual HMAC handshake. No debug port or token
export is needed. The upstream proxy buffers up to 640 KiB, for up to 50 s.
"""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import select
import socket
import stat
import struct
import time
from urllib.parse import urlsplit

import requests
from requests.adapters import BaseAdapter


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _proof(ticket, side, endpoint, client_nonce, server_nonce):
    parts = ["wbipc-s" if side == "server" else "wbipc-c", "1", endpoint,
             client_nonce, server_nonce]
    data = b"".join(struct.pack(">I", len(s.encode())) + s.encode() for s in parts)
    return _b64(hmac.new(ticket.encode(), data, hashlib.sha256).digest())


class WbipcError(requests.ConnectionError):
    pass


class WbipcAdapter(BaseAdapter):
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        try:
            return self._send(request, stream, timeout, verify, cert, proxies)
        except (OSError, ValueError, KeyError) as error:
            if isinstance(error, requests.RequestException):
                raise
            raise WbipcError("WorkBuddy 本机通信失败，请确认应用正在运行且接口版本兼容。") from None

    def _send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        home = Path(os.environ.get("WORKBUDDY_HOME", str(Path.home() / ".workbuddy")))
        try:
            discovery = json.loads((home / "wbipc" / "endpoint.json").read_text(encoding="utf-8"))
            endpoint, ticket = discovery["endpoint"], discovery["ticket"]
            if os.name == "nt":
                if not endpoint.startswith("\\\\.\\pipe\\wbipc-"):
                    raise ValueError("Unexpected pipe path")
            else:
                info = os.lstat(endpoint)
                if not os.path.isabs(endpoint) or not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("Untrusted Unix socket")
        except (OSError, ValueError, KeyError):
            raise WbipcError("未发现 WorkBuddy 通信接口，请先启动并登录 WorkBuddy。") from None

        wait = timeout[1] if isinstance(timeout, tuple) else timeout
        deadline = time.monotonic() + (wait or 60)
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                            ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            kernel.PeekNamedPipe.restype = wintypes.BOOL
            kernel.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
            kernel.WaitNamedPipeW.restype = wintypes.BOOL
            if not kernel.WaitNamedPipeW(endpoint, 5000):
                raise WbipcError("WorkBuddy 本机接口不可用，请确认应用仍在运行。")
            try:
                pipe = open(endpoint, "r+b", buffering=0)
            except OSError:
                raise WbipcError("无法连接 WorkBuddy 本机接口。") from None
            import msvcrt
            handle = msvcrt.get_osfhandle(pipe.fileno())

            def readable_bytes():
                available = wintypes.DWORD()
                if not kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                    raise WbipcError("WorkBuddy 通信连接已关闭。")
                return min(available.value, 65536)
        else:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                connection.settimeout(5)
                connection.connect(endpoint)
                connection.settimeout(None)
                pipe = connection.makefile("rwb", buffering=0)
            finally:
                connection.close()

            def readable_bytes():
                return 65536 if select.select([pipe], [], [], 0)[0] else 0

        with pipe:
            buffer = bytearray()

            def send_frame(frame):
                data = memoryview((json.dumps(frame, ensure_ascii=False) + "\n").encode("utf-8"))
                while data:
                    n = pipe.write(data)
                    if not n:
                        raise WbipcError("WorkBuddy 通信连接关闭。")
                    data = data[n:]

            def receive():
                while True:
                    if b"\n" in buffer:
                        line, _, tail = buffer.partition(b"\n")
                        buffer[:] = tail
                        return json.loads(line)
                    if len(buffer) > 2 * 1024 * 1024:
                        raise WbipcError("WorkBuddy 返回数据过大。")
                    if time.monotonic() > deadline:
                        raise requests.Timeout("WorkBuddy 本机接口超时。")
                    available = readable_bytes()
                    if available:
                        chunk = pipe.read(available)
                        if not chunk:
                            raise WbipcError("WorkBuddy 通信连接关闭。")
                        buffer.extend(chunk)
                    else:
                        time.sleep(0.02)

            nonce = _b64(secrets.token_bytes(16))
            send_frame({"type": "session_hello", "protocol_min": 1, "protocol_max": 1,
                        "client_nonce": nonce, "ticket_id": hashlib.sha256(ticket.encode()).hexdigest()[:16],
                        "client": {"kind": "python", "id": "wenxinyiyan", "version": "1"}})
            challenge = receive()
            server_nonce = challenge.get("server_nonce", "")
            expected = _proof(ticket, "server", endpoint, nonce, server_nonce)
            if challenge.get("type") != "session_challenge" or not hmac.compare_digest(expected, challenge.get("server_proof", "")):
                raise WbipcError("WorkBuddy 通信身份校验失败。")
            send_frame({"type": "session_prove", "client_proof": _proof(ticket, "client", endpoint, nonce, server_nonce)})
            ack = receive()
            if ack.get("type") != "session_hello_ack" or "wb.request" not in ack.get("pipes", []):
                raise WbipcError("WorkBuddy 未提供已登录的请求通道。")

            def rpc(identifier, method, params, mode=None):
                frame = {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}
                if mode:
                    frame["mode"] = mode
                send_frame(frame)
                while True:
                    reply = receive()
                    if reply.get("id") == identifier:
                        if "error" in reply:
                            # Do not log frame contents: discovery tickets and account data stay private.
                            raise WbipcError("WorkBuddy 请求通道拒绝调用或上游失败。")
                        return reply["result"]

            channel = rpc(1, "broker/GetPipe", {"pipe": "wb.request"})["channel"]
            body = request.body or b""
            if isinstance(body, str):
                body = body.encode("utf-8")
            parts = urlsplit(request.url)
            result = rpc(2, channel + "/http.fetch", {
                "method": request.method, "path": parts.path,
                "headers": {"content-type": "application/json", "accept": "text/event-stream"},
                "body_b64": base64.b64encode(body).decode("ascii"),
            }, "call")
            response = requests.Response()
            response.status_code = result["status"]
            response.headers.update(result.get("headers", {}))
            response._content = base64.b64decode(result["body_b64"], validate=True)
            response._content_consumed = True
            response.encoding = "utf-8"
            response.url = request.url
            response.request = request
            return response

    def close(self):
        pass
