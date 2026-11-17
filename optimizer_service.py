"""HTTP API for the WorkBuddy prompt bridge (Windows or Linux)."""
import hmac
import os
from pathlib import Path
import threading

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from workbuddy_optimizer import OptimizationError, optimize_prompt


class PromptRequest(BaseModel):
    text: str = Field(min_length=1, max_length=16000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, text):
        if not text.strip():
            raise ValueError("提示词不能为空")
        return text


class PromptResponse(BaseModel):
    status: str = "success"
    optimized_text: str


def create_app(optimizer=optimize_prompt, api_key=None):
    if api_key is None:
        api_key = os.environ.get("OPTIMIZER_API_KEY", "").strip()
        key_file = os.environ.get("OPTIMIZER_API_KEY_FILE")
        if key_file:
            api_key = Path(key_file).read_text(encoding="utf-8").strip()
        if (key_file or "OPTIMIZER_API_KEY" in os.environ) and not api_key:
            raise RuntimeError("Configured API key must not be empty")
    slots = threading.BoundedSemaphore(2)
    app = FastAPI(title="wenxinyiyan 提示词优化 API", version="1.0.0")

    def authorize(authorization: str | None = Header(default=None),
                  x_api_key: str | None = Header(default=None)):
        if not api_key:
            return
        supplied = x_api_key or (authorization[7:] if authorization and authorization.startswith("Bearer ") else "")
        if not hmac.compare_digest(supplied.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail="API key required")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready", dependencies=[Depends(authorize)])
    def ready():
        home = Path(os.environ.get("WORKBUDDY_HOME", str(Path.home() / ".workbuddy")))
        discovery = (home / "wbipc" / "endpoint.json").is_file()
        if not discovery and not os.environ.get("WORKBUDDY_AUTHORIZATION"):
            raise HTTPException(status_code=503, detail="WorkBuddy 未提供本机请求通道，请检查运行与登录状态")
        return {"status": "discovered", "note": "已发现通信配置；登录与调用状态以 /optimize 实际请求为准"}

    @app.post("/optimize", response_model=PromptResponse, dependencies=[Depends(authorize)])
    def optimize(request: PromptRequest):
        if not slots.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="正在处理其他请求，请稍后重试")
        try:
            return PromptResponse(optimized_text=optimizer(request.text, timeout=55))
        except OptimizationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
        finally:
            slots.release()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("OPTIMIZER_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "::1", "localhost") and not (os.environ.get("OPTIMIZER_API_KEY") or os.environ.get("OPTIMIZER_API_KEY_FILE")):
        raise SystemExit("监听局域网地址前必须配置 OPTIMIZER_API_KEY 或 OPTIMIZER_API_KEY_FILE")
    uvicorn.run(app, host=host, port=int(os.environ.get("OPTIMIZER_PORT", "18080")), access_log=False)
