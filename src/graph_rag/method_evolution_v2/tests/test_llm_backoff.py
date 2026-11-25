"""Tests for llm_client 429 backoff + error taxonomy (spec 一 + 二)."""
from __future__ import annotations

import os
import sys
import time
import unittest
from unittest.mock import patch

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_a import llm_client


class TestClassifyError(unittest.TestCase):

    def test_429(self):
        self.assertEqual(
            llm_client.classify_call_error({"ok": False,
                                              "error": "http_status=429"}),
            llm_client.ERROR_RATE_LIMIT)

    def test_401(self):
        self.assertEqual(
            llm_client.classify_call_error({"ok": False,
                                              "error": "http_status=401"}),
            llm_client.ERROR_AUTH)

    def test_403(self):
        self.assertEqual(
            llm_client.classify_call_error({"ok": False,
                                              "error": "http_status=403"}),
            llm_client.ERROR_AUTH)

    def test_network(self):
        self.assertEqual(
            llm_client.classify_call_error({"ok": False,
                                              "error": "request_exception: Timeout"}),
            llm_client.ERROR_NETWORK)

    def test_ok_returns_none(self):
        self.assertEqual(
            llm_client.classify_call_error({"ok": True, "error": ""}),
            llm_client.ERROR_NONE)


class TestCallChatWithBackoff(unittest.TestCase):

    def setUp(self):
        # Patch sleep to zero for fast tests
        self.sleep_patcher = patch("method_evolution_v2.stage_a.llm_client.time.sleep")
        self.mock_sleep = self.sleep_patcher.start()
        os.environ["MOONSHOT_API_KEY"] = "sk-test-only"

    def tearDown(self):
        self.sleep_patcher.stop()

    def test_backoff_returns_immediately_on_success(self):
        def fake_call(*a, **k):
            return {"ok": True, "text": "hi", "usage": {}, "raw": {},
                     "error": "", "http_status": 200, "model": "m"}
        with patch("method_evolution_v2.stage_a.llm_client.call_chat",
                    side_effect=fake_call) as mc:
            r = llm_client.call_chat_with_backoff("s", "u", model="m",
                                                     request_pace_sec=0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["error_type"], "")
        self.assertEqual(r["n_429_attempts"], 0)
        self.assertEqual(mc.call_count, 1)

    def test_backoff_retries_on_429_then_success(self):
        calls = []
        def fake_call(*a, **k):
            calls.append(len(calls))
            if len(calls) <= 2:
                return {"ok": False, "text": "", "usage": {}, "raw": {},
                         "error": "http_status=429", "http_status": 429,
                         "retry_after_header": None, "model": "m"}
            return {"ok": True, "text": "yes", "usage": {}, "raw": {},
                     "error": "", "http_status": 200, "model": "m"}
        with patch("method_evolution_v2.stage_a.llm_client.call_chat",
                    side_effect=fake_call):
            r = llm_client.call_chat_with_backoff("s", "u",
                                                     request_pace_sec=0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["error_type"], "")
        self.assertEqual(r["n_429_attempts"], 2)
        self.assertEqual(len(r["retry_log_429"]), 2)

    def test_backoff_gives_up_after_4_retries(self):
        def fake_call(*a, **k):
            return {"ok": False, "text": "", "usage": {}, "raw": {},
                     "error": "http_status=429", "http_status": 429,
                     "retry_after_header": None, "model": "m"}
        with patch("method_evolution_v2.stage_a.llm_client.call_chat",
                    side_effect=fake_call) as mc:
            r = llm_client.call_chat_with_backoff("s", "u",
                                                     request_pace_sec=0,
                                                     max_429_retries=4)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error_type"], llm_client.ERROR_RATE_LIMIT)
        # 1 initial + 4 retries = 5 calls
        self.assertEqual(mc.call_count, 5)
        self.assertEqual(r["n_429_attempts"], 5)

    def test_backoff_respects_retry_after_header(self):
        calls = []
        def fake_call(*a, **k):
            calls.append(len(calls))
            if len(calls) == 1:
                return {"ok": False, "text": "", "usage": {}, "raw": {},
                         "error": "http_status=429", "http_status": 429,
                         "retry_after_header": "7", "model": "m"}
            return {"ok": True, "text": "y", "usage": {}, "raw": {},
                     "error": "", "http_status": 200, "model": "m"}
        with patch("method_evolution_v2.stage_a.llm_client.call_chat",
                    side_effect=fake_call):
            r = llm_client.call_chat_with_backoff("s", "u",
                                                     request_pace_sec=0)
        self.assertTrue(r["ok"])
        # 检查 wait_seconds ≈ 7 (+ 0-2 jitter)
        wait = r["retry_log_429"][0]["wait_seconds"]
        self.assertGreaterEqual(wait, 7.0)
        self.assertLess(wait, 10.0)

    def test_backoff_stops_when_on_429_returns_true(self):
        def fake_call(*a, **k):
            return {"ok": False, "text": "", "usage": {}, "raw": {},
                     "error": "http_status=429", "http_status": 429,
                     "retry_after_header": None, "model": "m"}
        # driver 说: 第 1 次 429 就停
        with patch("method_evolution_v2.stage_a.llm_client.call_chat",
                    side_effect=fake_call) as mc:
            r = llm_client.call_chat_with_backoff("s", "u",
                                                     request_pace_sec=0,
                                                     on_429_response=lambda n: True)
        self.assertFalse(r["ok"])
        self.assertEqual(mc.call_count, 1)   # 未再重试
        self.assertIn("driver requested stop", r["error"])


class TestDecideRunActionRateLimitedPrior(unittest.TestCase):
    """spec 一: 之前 429 → 强制 run_api."""

    def setUp(self):
        import tempfile, json, shutil
        from method_evolution_v2.stage_a import full_runner as fr
        self._tempfile = tempfile
        self._json = json
        self._shutil = shutil
        self._fr = fr
        self.tmp = tempfile.mkdtemp()
        self.pid = "rate-limited-test"
        self.md_path = os.path.join(self.tmp, "full.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("some content")
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)
        d = fr.per_paper_dir(self.pid, self.base)
        os.makedirs(d, exist_ok=True)
        # seed matched manifest (would normally skip)
        m = fr.build_input_manifest(self.pid, self.md_path, model="test")
        with open(os.path.join(d, "input_manifest.json"),
                    "w", encoding="utf-8") as f:
            json.dump(m, f)
        with open(os.path.join(d, "validation_report.json"),
                    "w", encoding="utf-8") as f:
            json.dump({"n_accepted": 0}, f)
        # raw_response says prior 429 fail
        with open(os.path.join(d, "raw_response.json"),
                    "w", encoding="utf-8") as f:
            json.dump({"own_methods_raw": [], "referenced_methods_raw": [],
                        "json_parse_ok": False,
                        "json_parse_error": "http_status=429"}, f)

    def tearDown(self):
        self._shutil.rmtree(self.tmp, ignore_errors=True)

    def test_prior_429_returns_run_api(self):
        current = self._fr.build_input_manifest(self.pid, self.md_path,
                                                    model="test")
        action, reason = self._fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertEqual(reason, "prior_call_rate_limited")


if __name__ == "__main__":
    unittest.main(verbosity=2)
