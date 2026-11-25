"""Bounded JSON tasks for Kimi, without altering the legacy LLM compatibility layer.

Moonshot K2.6 defaults to reasoning, which can consume a short output budget before
any JSON is emitted. Extraction, planning and complete native JSON answers use
instant mode. Unsupported clients retain their legacy path; the existing key/model
are reused. Native answer completeness does not establish factual correctness.
"""
from urllib.parse import urlparse


def call_structured(llm, prompt, max_tokens=4000, _attempt=0, thinking=False):
    model = str(getattr(llm, "model", ""))
    base = str(getattr(llm, "base_url", ""))
    hostname = urlparse(base).hostname
    if model not in {"kimi-k2.5", "kimi-k2.6"} or hostname not in {"api.moonshot.cn", "api.moonshot.ai"}:
        return llm.call_llm(prompt=prompt, temperature=0.0, max_tokens=max_tokens)
    import requests
    import time
    started = time.monotonic()
    if not hasattr(llm, 'structured_calls'):
        llm.structured_calls = []
    def failure(kind, status=None):
        llm.structured_calls.append({'purpose': 'structured_semantic' if thinking else 'structured_json',
            'model': model, 'thinking': 'enabled' if thinking else 'disabled',
            'temperature': 1.0 if thinking else 0.6, 'max_tokens': max_tokens,
            'api_attempt': _attempt + 1, 'error': kind, 'http_status': status,
            'seconds': round(time.monotonic() - started, 3), 'usage': None})
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 1.0 if thinking else 0.6, "max_tokens": max_tokens, "stream": thinking,
               "response_format": {"type": "json_object"},
               "thinking": {"type": "enabled" if thinking else "disabled"}}
    if thinking:
        payload['stream_options'] = {'include_usage': True}
    try:
        response = requests.post(base.rstrip("/") + "/chat/completions", json=payload,
                                 headers={"Authorization": "Bearer " + llm.api_key,
                                          "Content-Type": "application/json"}, timeout=(30, 90), stream=thinking)
        with response:
            if response.status_code != 200:
                failure('http_error', response.status_code)
                if response.status_code in {429, 500, 502, 503, 504} and _attempt == 0:
                    return call_structured(llm, prompt, max_tokens, _attempt=1, thinking=thinking)
                try:
                    error = response.json().get("error") or {}
                except (ValueError, AttributeError):
                    error = {}
                # API diagnostics contain parameter names, never authorization headers.
                import re
                message = re.sub(r"sk-[A-Za-z0-9._-]+", "[REDACTED]", str(error.get("message") or ""))[:400]
                return f"❌ 结构化调用 HTTP {response.status_code}: {error.get('type', '')} {message}"
            if thinking:
                import json
                content, usage, finish = [], {}, None
                for line in response.iter_lines():
                    if not line or not line.startswith(b'data:'):
                        continue
                    item = line[5:].strip()
                    if item == b'[DONE]':
                        break
                    chunk = json.loads(item)
                    if chunk.get('usage'):
                        usage = chunk['usage']
                    for part in chunk.get('choices') or []:
                        if part.get('finish_reason'):
                            finish = part['finish_reason']
                        content.append(str((part.get('delta') or {}).get('content') or ''))
                if finish is None:
                    raise ValueError('Incomplete semantic audit stream')
                data = {'choices': [{'message': {'content': ''.join(content)}, 'finish_reason': finish}],
                        'usage': usage}
            else:
                data = response.json()
        choice = (data.get("choices") or [{}])[0]
        usage = dict(data.get("usage") or {})
        event = {"purpose": "structured_semantic" if thinking else "structured_json", "model": model,
                 "thinking": "enabled" if thinking else "disabled",
                 "temperature": 1.0 if thinking else 0.6,
                 "max_tokens": max_tokens, "finish_reason": choice.get("finish_reason"),
                 "api_attempt": _attempt + 1, 'seconds': round(time.monotonic() - started, 3),
                 'response_format': 'json_object',
                 "usage": usage or None}
        if not hasattr(llm, "structured_calls"):
            llm.structured_calls = []
        llm.structured_calls.append(event)
        if choice.get("finish_reason") == "length":
            return "❌ 结构化输出达到长度上限，拒绝不完整 JSON"
        return str((choice.get("message") or {}).get("content") or "").strip()
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        failure(type(exc).__name__)
        if _attempt == 0:
            return call_structured(llm, prompt, max_tokens, _attempt=1, thinking=thinking)
        return f"❌ 结构化调用失败或响应格式异常: {type(exc).__name__}"
