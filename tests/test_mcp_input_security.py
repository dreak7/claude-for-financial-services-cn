import importlib.util
import json
import sys
import types
import unittest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd


class FastMCPStub:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        return lambda function: function


mcp = types.ModuleType("mcp")
mcp.FastMCP = FastMCPStub
sys.modules["mcp"] = mcp
akshare = types.ModuleType("akshare")
for name in (
    "stock_info_a_code_name", "stock_zh_a_hist", "stock_financial_abstract_ths",
    "stock_info_global_em", "stock_zh_a_spot_em",
):
    setattr(akshare, name, Mock())
sys.modules["akshare"] = akshare
ROOT = Path(__file__).parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


akshare_server = load("akshare_server_input_test", "mcp-servers/akshare-mcp/server.py")
news_server = load("news_server_input_test", "mcp-servers/china-news-mcp/server.py")
ifind = load("ifind_server_input_test", "mcp-servers/ifind-mcp/server.py")


class InputValidationTest(unittest.TestCase):
    def test_stock_search_treats_keyword_as_literal_text(self):
        df = pd.DataFrame({"code": ["000001", "600519"], "name": ["平安[银行", "贵州茅台"]})
        with patch.object(akshare_server.ak, "stock_info_a_code_name", return_value=df):
            result = json.loads(akshare_server.search_stock("["))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "000001")

    def test_invalid_history_frequency_does_not_call_upstream(self):
        with patch.object(akshare_server.ak, "stock_zh_a_hist") as call:
            result = json.loads(akshare_server.get_historical_data("600519", frequency="hourly"))
        self.assertIn("error", result)
        call.assert_not_called()

    def test_invalid_financial_period_does_not_call_upstream(self):
        with patch.object(akshare_server.ak, "stock_financial_abstract_ths") as call:
            result = json.loads(akshare_server.get_financials("600519", period="monthly"))
        self.assertIn("error", result)
        call.assert_not_called()

    def test_negative_headline_count_returns_empty_list(self):
        df = pd.DataFrame({"标题": ["a", "b", "c"]})
        with patch.object(news_server.ak, "stock_info_global_em", return_value=df):
            result = json.loads(news_server.get_market_headlines(-1))
        self.assertEqual(result, [])

    def test_upstream_exception_is_not_returned_to_caller(self):
        with patch.object(akshare_server.ak, "stock_zh_a_spot_em", side_effect=Exception("secret-token")):
            result = json.loads(akshare_server.get_quote("600519"))
        self.assertNotIn("secret-token", result["error"])


class IfindConcurrencyTest(unittest.TestCase):
    def test_initialization_error_is_sanitized(self):
        with (
            patch.object(ifind, "AUTH_TOKEN", "token"),
            patch.object(ifind, "_init_session", side_effect=RuntimeError("secret-token")),
        ):
            result = json.loads(ifind._call_ifind("stock", "search_stocks", {}))
        self.assertIn("error", result)
        self.assertNotIn("secret-token", result["error"])

    def test_request_ids_are_generated_under_lock(self):
        lock = MagicMock()
        with patch.object(ifind, "_lock", lock):
            ifind._next_id("stock")
        lock.__enter__.assert_called_once()
        lock.__exit__.assert_called_once()

    def test_tool_calls_wait_for_initialization_notification(self):
        response = Mock(headers={"Mcp-Session-Id": "session"})
        notify_started = threading.Event()
        finish_notify = threading.Event()
        tool_calls = []
        ifind._sessions.clear()

        def post(server_type, payload, timeout=60):
            if payload["method"] == "initialize":
                return response, {}
            tool_calls.append(payload)
            return response, {}

        def notify(*args, **kwargs):
            notify_started.set()
            finish_notify.wait(2)
            return response

        with (
            patch.object(ifind, "AUTH_TOKEN", "token"),
            patch.object(ifind, "_post", side_effect=post),
            patch.object(ifind._session, "post", side_effect=notify),
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(ifind._call_ifind, "stock", "first", {})
                self.assertTrue(notify_started.wait(1))
                second = pool.submit(ifind._call_ifind, "stock", "second", {})
                time.sleep(0.05)
                self.assertEqual(tool_calls, [])
                finish_notify.set()
                first.result(timeout=2)
                second.result(timeout=2)
        self.assertEqual(len(tool_calls), 2)

    def test_concurrent_session_initialization_runs_once(self):
        response = Mock(headers={"Mcp-Session-Id": "session"})
        ifind._sessions.clear()

        def slow_post(*args, **kwargs):
            time.sleep(0.05)
            return response, {}

        with (
            patch.object(ifind, "_post", side_effect=slow_post) as post,
            patch.object(ifind._session, "post"),
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: ifind._init_session("stock"), range(2)))
        self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
