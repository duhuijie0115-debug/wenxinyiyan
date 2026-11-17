"""Per-user hotkey supervisor and short-lived HTTP worker. Logs contain no prompts."""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

import requests

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "desktop"
STATE = HERE / "state"
CONFIG = HERE / "settings.json"
MUTEXES = []


def settings():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def session():
    client = requests.Session()
    client.trust_env = False  # LAN traffic must not go through a system proxy.
    return client


def api_headers(config):
    key_path = ROOT / config.get("api_key_file", ".wenxinyiyan-api-key")
    return {"X-API-Key": key_path.read_text(encoding="utf-8").strip()}


def acquire_mutex(name):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)
        return False
    MUTEXES.append(handle)
    return True


def logger():
    STATE.mkdir(exist_ok=True)
    log = logging.getLogger("optimizer-desktop")
    if not log.handlers:
        handler = RotatingFileHandler(STATE / "agent.log", maxBytes=256_000,
                                      backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def notify(message):
    # Modal only for failures requiring a human action; never steals focus on success.
    ctypes.windll.user32.MessageBoxW(None, message, "wenxinyiyan 提示词优化", 0x40)


def start_login():
    if not acquire_mutex("Local\\WenxinyiyanLogin"):
        return
    config = settings()
    if not config.get("automatic_login_assistance", True):
        return
    relay = subprocess.Popen(
        [sys.executable, str(ROOT / "deployment" / "desktop_tunnel.py"),
         "--ssh-host", config.get("ssh_host", "feiniu"),
         "--local-port", str(config.get("desktop_local_port", 16080)),
         "--remote-port", str(config.get("desktop_remote_port", 16080))],
        cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with session() as client:
            for _ in range(20):
                try:
                    r = client.get(f"http://127.0.0.1:{config.get('desktop_local_port', 16080)}/vnc.html", timeout=10)
                    if r.status_code == 200:
                        break
                except requests.RequestException:
                    time.sleep(1)
            else:
                notify("登录桌面连接失败。请确认飞牛在线、SSH 别名 feiniu 可用，再从托盘选择重新登录。")
                return
        webbrowser.open(f"http://127.0.0.1:{config.get('desktop_local_port', 16080)}/vnc.html?autoconnect=1&resize=scale")
        # Desktop access is temporary; NAS WorkBuddy continues after relay closes.
        time.sleep(15 * 60)
    finally:
        if relay.poll() is None:
            relay.terminate()
            relay.wait(timeout=10)


def launch_login_if_due():
    marker = STATE / "login-assistance.timestamp"
    if marker.exists() and time.time() - marker.stat().st_mtime < 1800:
        return
    marker.touch()
    subprocess.Popen([sys.executable, str(__file__), "--login"], cwd=ROOT,
                     creationflags=subprocess.CREATE_NO_WINDOW)


def optimize(text, config):
    if not isinstance(text, str) or not text.strip() or len(text) > 16000:
        return {"ok": False, "error": "请选择 1～16000 字符的文本。"}
    try:
        with session() as client:
            response = client.post(config["api_url"].rstrip("/") + "/optimize",
                                   json={"text": text}, headers=api_headers(config), timeout=(5, 65))
        try:
            data = response.json()
        except ValueError:
            return {"ok": False, "error": "接口返回格式异常，请稍后重试。"}
        if response.status_code == 200:
            result = data.get("optimized_text")
            if isinstance(result, str) and result.strip():
                return {"ok": True, "text": result}
            return {"ok": False, "error": "接口未返回优化文本。"}
        detail = str(data.get("detail", ""))
        if response.status_code == 502 and any(x in detail for x in ("登录", "鉴权", "权限不足")):
            if config.get("automatic_login_assistance", True):
                launch_login_if_due()
            return {"ok": False, "error": "WorkBuddy 登录已失效，已尝试打开登录桌面。请扫码后重试。"}
        messages = {401: "本机 API 密钥与服务端不一致，请检查 .wenxinyiyan-api-key。",
                    429: "优化服务正忙，请稍后再按快捷键。",
                    422: "文本超长或格式无效。"}
        return {"ok": False, "error": messages.get(response.status_code,
                f"优化失败（HTTP {response.status_code}），请稍后重试。")}
    except requests.Timeout:
        return {"ok": False, "error": "请求超时，原文未被替换。请稍后重试。"}
    except requests.RequestException:
        return {"ok": False, "error": "无法连接飞牛，请检查局域网。恢复连接后可直接重试。"}
    except (OSError, ValueError, KeyError):
        return {"ok": False, "error": "本机配置或 API 密钥文件不可用。"}


def worker(request_file):
    """Only this worker's response file is consumed; always delete input promptly."""
    request_file = Path(request_file).resolve()
    if request_file.parent != STATE.resolve():
        raise ValueError("Unexpected request path")
    output = request_file.with_suffix(".out")
    try:
        text = request_file.read_text(encoding="utf-8-sig")
    finally:
        request_file.unlink(missing_ok=True)
    result = optimize(text, settings())
    # Separate files avoid requiring a bundled AHK JSON parser.
    payload = ("OK\n" + result["text"]) if result["ok"] else ("ERROR\n" + result["error"])
    temporary = output.with_suffix(".pending")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(output)


def maintenance(stop, log):
    previous = None
    while not stop.is_set():
        try:
            config = settings()
            with session() as client:
                r = client.get(config["api_url"].rstrip("/") + "/ready",
                               headers=api_headers(config), timeout=(3, 5))
            state = str(r.status_code)
        except (requests.RequestException, OSError, ValueError, KeyError):
            state = "offline-or-config-error"
        if state != previous:
            log.info("readiness=%s (discovery only, not login validation)", state)
            previous = state
        # Crash leftovers are removed; live prompts are never logged.
        for pattern in ("request-*.txt", "request-*.out", "request-*.pending"):
            for path in STATE.glob(pattern):
                try:
                    if time.time() - path.stat().st_mtime > 600:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
        stop.wait(60)


def supervise():
    if not acquire_mutex("Local\\WenxinyiyanSupervisor"):
        return
    log = logger()
    stop = threading.Event()
    threading.Thread(target=maintenance, args=(stop, log), daemon=True).start()
    delay = 2
    try:
        while True:
            started = time.monotonic()
            with (STATE / "hotkey-startup.log").open("w", encoding="utf-8") as errors:
                process = subprocess.Popen([str(HERE / "runtime" / "AutoHotkey64.exe"),
                                            "/ErrorStdOut=UTF-8", str(HERE / "optimizer.ahk")],
                                           cwd=ROOT, stdout=errors, stderr=errors)
                code = process.wait()
            if code == 0:  # User explicitly exits from tray.
                break
            log.warning("hotkey process exited code=%d; restarting", code)
            time.sleep(delay)
            delay = 2 if time.monotonic() - started > 60 else min(delay * 2, 60)
    finally:
        stop.set()


def main():
    STATE.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    parser.add_argument("--login", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.login:
        start_login()
    else:
        supervise()


if __name__ == "__main__":
    main()
