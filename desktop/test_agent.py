import unittest
from unittest.mock import Mock, patch
import requests
from desktop import agent


class WorkerTests(unittest.TestCase):
    def call(self, status=200, body=None, error=None):
        response = Mock(status_code=status)
        response.json.return_value = body or {"optimized_text": "优化结果"}
        client = Mock()
        client.post.return_value = response
        if error:
            client.post.side_effect = error
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=False)
        with patch.object(agent, "session", return_value=context), \
             patch.object(agent, "api_headers", return_value={"X-API-Key": "test"}), \
             patch.object(agent, "launch_login_if_due") as login:
            result = agent.optimize("测试原文", {"api_url": "http://nas:18080"})
        return result, client, login

    def test_success_and_exact_input(self):
        result, client, _ = self.call()
        self.assertEqual(result, {"ok": True, "text": "优化结果"})
        self.assertEqual(client.post.call_args.kwargs["json"], {"text": "测试原文"})

    def test_login_assistance_only_for_login_failure(self):
        result, _, login = self.call(502, {"detail": "WorkBuddy 未提供已登录的请求通道。"})
        self.assertFalse(result["ok"])
        login.assert_called_once()
        _, _, login = self.call(401, {"detail": "API key required"})
        login.assert_not_called()

    def test_timeout_is_not_retried(self):
        result, client, login = self.call(error=requests.Timeout())
        self.assertFalse(result["ok"])
        self.assertEqual(client.post.call_count, 1)
        login.assert_not_called()

    def test_invalid_input_never_reaches_network(self):
        with patch.object(agent, "session") as factory:
            for value in ("", " ", "x" * 16001):
                self.assertFalse(agent.optimize(value, {})["ok"])
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
