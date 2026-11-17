import json
from pathlib import Path
import unittest
from unittest.mock import patch

import requests
import workbuddy_optimizer as bridge

ROOT = Path(__file__).resolve().parent


def response_with(body):
    response = requests.Response()
    response.status_code = 200
    response._content = body.encode("utf-8")
    response._content_consumed = True
    return response


class BridgeTests(unittest.TestCase):
    def test_complete_sse_fixture(self):
        stream = (ROOT / "tests/fixtures/completion.sse").read_text(encoding="utf-8")
        expected = "测试优化结果"
        self.assertEqual(bridge._read_completion(response_with(stream)), expected)

    def test_disconnect_does_not_return_partial_success(self):
        stream = 'data: {"choices":[{"delta":{"content":"部分文本"}}]}\n\n'
        with self.assertRaisesRegex(bridge.OptimizationError, "提前断开"):
            bridge._read_completion(response_with(stream))

    def test_reasoning_is_excluded_and_multiline_sse_is_supported(self):
        stream = ('data: {"choices":\n'
                  'data: [{"delta":{"content":"结果","reasoning_content":"不应输出"}}]}\n\n'
                  'data: [DONE]\n\n')
        self.assertEqual(bridge._read_completion(response_with(stream)), "结果")

    def test_literal_backslashes_survive_prompt_insertion(self):
        original = '整理 C:\\new\\test 路径，保留 \\1 字符。\n第二行'
        with patch.object(bridge, "_login_headers", return_value={}):
            _, payload = bridge._request_parts(original)
        user = next(m for m in payload["messages"] if m["role"] == "user")
        text = user["content"][0]["text"]
        self.assertIn(original, text)
        self.assertNotIn("WB_OPT_20261117", text)


if __name__ == "__main__":
    unittest.main()
