import unittest
import os
from unittest.mock import patch
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from optimizer_service import create_app
from workbuddy_optimizer import OptimizationError


class ServiceTests(unittest.TestCase):
    def test_configured_empty_key_fails_closed(self):
        with patch.dict(os.environ, {"OPTIMIZER_API_KEY": "  "}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must not be empty"):
                create_app()

    def test_concurrency_limit_and_release(self):
        started = threading.Barrier(3)
        release = threading.Event()
        def backend(*args, **kwargs):
            started.wait(timeout=5)
            release.wait(timeout=5)
            return "结果"
        client = TestClient(create_app(backend, api_key=""))
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(client.post, "/optimize", json={"text": "测试"}) for _ in range(2)]
            try:
                started.wait(timeout=5)
                self.assertEqual(client.post("/optimize", json={"text": "测试"}).status_code, 429)
            finally:
                release.set()
            self.assertTrue(all(f.result().status_code == 200 for f in pending))

    def test_authentication_and_original_text(self):
        calls = []
        def backend(text, **kwargs):
            calls.append(text)
            return "增强结果"
        client = TestClient(create_app(backend, api_key="test-secret"))
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.post("/optimize", json={"text": "原文"}).status_code, 401)
        result = client.post("/optimize", json={"text": " 原文\\路径 "},
                             headers={"X-API-Key": "test-secret"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["optimized_text"], "增强结果")
        self.assertEqual(calls, [" 原文\\路径 "])

    def test_invalid_input_and_backend_failure(self):
        def backend(*args, **kwargs):
            raise OptimizationError("请重新登录")
        client = TestClient(create_app(backend, api_key=""))
        for text in ("", "  ", "x" * 16001):
            self.assertEqual(client.post("/optimize", json={"text": text}).status_code, 422)
        for _ in range(3):
            result = client.post("/optimize", json={"text": "原文"})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.json()["detail"], "请重新登录")


if __name__ == "__main__":
    unittest.main()
