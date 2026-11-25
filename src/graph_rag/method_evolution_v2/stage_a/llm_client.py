"""Moonshot (Kimi) HTTP 客户端 - 只从 MOONSHOT_API_KEY 环境变量读 key.

设计约束(spec 五):
  - 源码不含任何 API key
  - key 必须由 MOONSHOT_API_KEY 环境变量提供; 未设 → 抛异常
  - 返回结构: {"ok": bool, "text": str, "usage": {...}, "raw": {...}, "error": str}
  - 不重试 (由外层 driver 控制重试策略)
  - 明确超时, 不无限等待
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime

import requests


# 错误分类 (spec 一)
ERROR_RATE_LIMIT = "rate_limit_429"
ERROR_AUTH = "authentication_error"
ERROR_NETWORK = "network_error"
ERROR_JSON_PARSE = "json_parse_error"
ERROR_VALIDATION = "validation_error"
ERROR_NONE = ""


def classify_call_error(r: dict) -> str:
    """spec 一: 把 call_chat 的错误结果分类."""
    if r.get("ok"):
        return ERROR_NONE
    err = (r.get("error") or "").lower()
    if "http_status=429" in err:
        return ERROR_RATE_LIMIT
    if "http_status=401" in err or "http_status=403" in err \
            or "invalid_authentication" in err:
        return ERROR_AUTH
    if "request_exception" in err or "non_json_response" in err \
            or "network" in err or "timeout" in err:
        return ERROR_NETWORK
    return ERROR_NETWORK   # 其他 HTTP 5xx 归网络类


def _extract_retry_after(r: dict) -> float | None:
    """从 raw body 或 header 里读 Retry-After (秒).

    我们目前在 call_chat 里没显式保存 header, 但可能在 body 里出现;
    保守做法: 无则返回 None, 让上层用指数退避.
    """
    raw = r.get("raw") or {}
    # Moonshot 有时候在 error.body 里放; 兜底搜任何 retry_after key
    def _walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k.lower() in ("retry-after", "retry_after"):
                    try:
                        return float(x)
                    except (ValueError, TypeError):
                        pass
                r2 = _walk(x)
                if r2 is not None: return r2
        return None
    return _walk(raw)


MOONSHOT_API_URL = "https://api.moonshot.cn/v1/chat/completions"

DEFAULT_MODEL = os.environ.get("MOONSHOT_MODEL", "kimi-k2-0711-preview")
DEFAULT_TIMEOUT = 300      # 秒
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 6000


def get_api_key() -> str:
    """从环境变量读 key. 未设置 → RuntimeError.

    严禁在源码中写入任何 fallback key.
    """
    k = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if not k:
        raise RuntimeError(
            "MOONSHOT_API_KEY environment variable is not set. "
            "Stage A requires an LLM key exclusively from env. "
            "Please `export MOONSHOT_API_KEY=<your-key>` and re-run."
        )
    return k


def call_chat(system_prompt: str, user_prompt: str,
              model: str = None, temperature: float = DEFAULT_TEMPERATURE,
              max_tokens: int = DEFAULT_MAX_TOKENS,
              timeout: int = DEFAULT_TIMEOUT,
              force_json: bool = True) -> dict:
    """单次 Chat Completions 调用. 不重试.

    Returns:
      {
        "ok": bool,
        "text": <str, LLM 返回内容>,
        "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...},
        "raw":   <完整 API 返回 dict>,
        "error": <str, ok=False 时>,
        "model": <str, 实际使用的 model name>,
      }
    """
    key = get_api_key()
    model = model or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            MOONSHOT_API_URL, headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=timeout,
        )
    except requests.RequestException as e:
        return {"ok": False, "text": "", "usage": {}, "raw": {},
                "error": f"request_exception: {type(e).__name__}: {e}",
                "model": model}

    if resp.status_code != 200:
        # 尝试 JSON 化错误
        try:
            body = resp.json()
        except Exception:
            body = {"raw_text": resp.text[:1000]}
        # 保留响应头 (spec 二: 429 时读 Retry-After)
        header_retry_after = resp.headers.get("Retry-After") \
                                or resp.headers.get("retry-after")
        return {"ok": False, "text": "", "usage": {}, "raw": body,
                "error": f"http_status={resp.status_code}",
                "http_status": resp.status_code,
                "retry_after_header": header_retry_after,
                "model": model}

    try:
        data = resp.json()
    except Exception as e:
        return {"ok": False, "text": "", "usage": {}, "raw": {"raw_text": resp.text[:1000]},
                "error": f"non_json_response: {e}",
                "model": model}

    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        return {"ok": False, "text": "", "usage": data.get("usage") or {},
                "raw": data, "error": "no_content_in_response",
                "model": model}

    return {
        "ok": True,
        "text": text,
        "usage": data.get("usage") or {},
        "raw": data,
        "error": "",
        "http_status": 200,
        "model": model,
    }


# spec 二: 429 指数退避基础 (秒)
BACKOFF_BASES_429 = (10, 30, 60, 120)
MAX_429_RETRIES = 4
DEFAULT_REQUEST_PACE_SEC = 1.5
DEFAULT_JITTER_MAX_SEC = 2.0


def call_chat_with_backoff(system_prompt: str, user_prompt: str,
                              model: str = None,
                              max_429_retries: int = MAX_429_RETRIES,
                              request_pace_sec: float = DEFAULT_REQUEST_PACE_SEC,
                              on_429_response=None,
                              **kwargs) -> dict:
    """spec 二: 单个请求, 遇 429 自动指数退避重试 (最多 4 次).

    - 优先读响应 Retry-After header (秒)
    - 无则用基础 [10, 30, 60, 120] + 随机抖动
    - 每次重试均记录到 retry_log_429
    - JSON 解析重试与 429 重试彻底分开
    - on_429_response: callable(consec_429_count_now) → bool
        由 driver 传入以实现"连续 5 次 429 立即停止". 返回 True 则中止重试.

    Returns:
      call_chat 相同结构 + 新增:
        error_type: rate_limit_429 / authentication_error / network_error /
                    json_parse_error / ""
        retry_log_429: [{at_iso, attempt, http_status, wait_seconds}]
        n_429_attempts: 本次调用一共遇到多少次 429
    """
    retry_log = []
    n_429 = 0
    for attempt in range(1, max_429_retries + 2):
        # 请求间隔 (spec 二: 正常请求之间 1-2 秒)
        if attempt == 1 and request_pace_sec > 0:
            time.sleep(request_pace_sec
                          + random.uniform(0, DEFAULT_JITTER_MAX_SEC))
        r = call_chat(system_prompt, user_prompt, model=model, **kwargs)
        err_type = classify_call_error(r)
        r["error_type"] = err_type
        if err_type != ERROR_RATE_LIMIT:
            r["retry_log_429"] = retry_log
            r["n_429_attempts"] = n_429
            return r
        n_429 += 1
        # 通知 driver, 可让其立即停止
        if on_429_response is not None:
            try:
                if on_429_response(n_429):
                    r["retry_log_429"] = retry_log
                    r["n_429_attempts"] = n_429
                    r["error"] = f"http_status=429 (driver requested stop)"
                    return r
            except Exception:
                pass
        if attempt > max_429_retries:
            # 上限 → 放弃
            r["retry_log_429"] = retry_log
            r["n_429_attempts"] = n_429
            r["error"] = f"http_status=429 (after {n_429} retries)"
            return r
        # 计算等待秒数
        ra = r.get("retry_after_header")
        if ra:
            try:
                base = float(ra)
            except (ValueError, TypeError):
                base = BACKOFF_BASES_429[min(attempt - 1,
                                                 len(BACKOFF_BASES_429) - 1)]
        else:
            base = BACKOFF_BASES_429[min(attempt - 1,
                                             len(BACKOFF_BASES_429) - 1)]
        jitter = random.uniform(0, DEFAULT_JITTER_MAX_SEC)
        wait = base + jitter
        retry_log.append({
            "at_iso": datetime.now().isoformat(timespec="seconds"),
            "attempt": attempt,
            "http_status": 429,
            "wait_seconds": round(wait, 2),
        })
        time.sleep(wait)
    # unreachable
    r["retry_log_429"] = retry_log
    r["n_429_attempts"] = n_429
    return r
