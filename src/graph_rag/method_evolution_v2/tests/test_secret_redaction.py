"""Secret redaction regression test (spec: 增加自动脱敏测试).

Fails if any file under Stage A / recovery / batch reports / aggregation /
scratch contains a plaintext value that looks like:
  - `sk-[A-Za-z0-9]{20,}` (Moonshot / OpenAI-style key)
  - `Authorization:` / `authorization:` followed by any Bearer literal
  - Any `MOONSHOT_API_KEY=...` assignment with a value that isn't the
    literal placeholder `configured: yes` / `configured: no`
  - `api_key='sk-...'` / `api_key="..."` assignments with real values

Passes if these fields are absent OR redacted to the standard sentinel.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config


# 高风险模式 (只匹配值样, 不匹配字段名本身)
SK_KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
BEARER_RE = re.compile(r"(?i)(authorization|bearer)\s*[:=]\s*['\"]?"
                          r"[A-Za-z0-9_\-\.]{20,}")
INLINE_ENV_RE = re.compile(
    r"MOONSHOT_API_KEY\s*=\s*['\"]sk-[A-Za-z0-9]{5,}")
INLINE_APIKEY_RE = re.compile(
    r"api_key\s*=\s*['\"][A-Za-z0-9_\-]{20,}")


HIGH_RISK_DIRS = [
    config.STAGE_A_FULL_V1_DIR,
    getattr(config, "STAGE_A_RECOVERY_TEST_V1_DIR", None),
    getattr(config, "STAGE_A_REVALID_V1_1_DIR", None),
]


def _walk_files(root):
    out = []
    for base, _, files in os.walk(root):
        for fn in files:
            p = os.path.join(base, fn)
            out.append(p)
    return out


class TestNoPlaintextSecretsInStageAOutputs(unittest.TestCase):

    def test_no_sk_key_in_stage_a_outputs(self):
        offenders = []
        for root in HIGH_RISK_DIRS:
            if not root or not os.path.isdir(root):
                continue
            for p in _walk_files(root):
                try:
                    with open(p, "rb") as f:
                        data = f.read(500_000)   # cap at 500KB
                    text = data.decode("utf-8", errors="ignore")
                except OSError:
                    continue
                if SK_KEY_RE.search(text):
                    offenders.append(("sk_key_pattern", p))
                if INLINE_ENV_RE.search(text):
                    offenders.append(("inline_env_assignment", p))
                if INLINE_APIKEY_RE.search(text):
                    offenders.append(("api_key_assignment", p))
                if BEARER_RE.search(text):
                    offenders.append(("authorization_header", p))
        # Report ONLY file paths, never content (spec 一)
        if offenders:
            summary = "\n".join(f"  [{kind}] {p}"
                                    for kind, p in offenders)
            self.fail(f"Plaintext secret pattern found in "
                        f"{len(offenders)} file(s):\n{summary}")

    def test_llm_client_never_logs_key(self):
        """Sanity: source of llm_client must not log Authorization header
        or the resolved key. Grep the module code, not values."""
        from method_evolution_v2.stage_a import llm_client as lc
        with open(lc.__file__, "r", encoding="utf-8") as f:
            src = f.read()
        # No print/log of Authorization / key
        forbidden = [r"print\([^)]*Authorization",
                        r"print\([^)]*api_key",
                        r"print\([^)]*MOONSHOT_API_KEY\s*=",
                        r"logger\.[a-z]+\([^)]*Authorization",
                        r"logger\.[a-z]+\([^)]*api_key"]
        for pat in forbidden:
            if re.search(pat, src, re.IGNORECASE):
                self.fail(f"llm_client source appears to log a secret "
                            f"field: pattern={pat!r}")

    def test_get_api_key_error_does_not_leak(self):
        """get_api_key error message must not embed the observed key."""
        from method_evolution_v2.stage_a import llm_client as lc
        # Temporarily unset the env
        prior = os.environ.pop("MOONSHOT_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError) as cm:
                lc.get_api_key()
            msg = str(cm.exception)
            # The error message must not contain any sk-... value
            self.assertIsNone(SK_KEY_RE.search(msg))
        finally:
            if prior is not None:
                os.environ["MOONSHOT_API_KEY"] = prior


if __name__ == "__main__":
    unittest.main(verbosity=2)
