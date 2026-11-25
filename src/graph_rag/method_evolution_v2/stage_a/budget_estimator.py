"""Stage A 全量运行预算估算 (dry-run, 无 API).

三种估算 (spec 七):
  1. empirical_linear   - 从 v03 10 篇实际运行按 (per-paper) × 337 线性外推
  2. per_token_actual   - 对每篇实际构建 sentence pack, 按 chars→token 估算 * 单价
  3. worst_case         - 全部 128k tier + 全部重试 = 2× 上限

价目来源: Moonshot 官网 (2024-2025 公开报价). 若无法确认, 明确标记 "estimated_price".
"""
from __future__ import annotations

import os


# ---- Moonshot 参考价 (估算价目; 官方账单为准) ----
# 单位: 人民币 / 百万 token
MOONSHOT_PRICING_CNY_PER_M = {
    "moonshot-v1-8k":    {"input": 12.0, "output": 12.0},
    "moonshot-v1-32k":   {"input": 24.0, "output": 24.0},
    "moonshot-v1-128k":  {"input": 60.0, "output": 60.0},
    "kimi-latest":       {"input": 12.0, "output": 12.0},   # 参考
}
DEFAULT_MODEL = "moonshot-v1-auto"

# 各 tier 的 tokens 阈值 (输入 tokens 决定路由)
TIER_THRESHOLDS = [
    ("moonshot-v1-8k",   8_000),
    ("moonshot-v1-32k",  32_000),
    ("moonshot-v1-128k", 128_000),
]

# chars → tokens 估算 (v03 实测: total_tokens / section_pack_chars ~ 0.5)
# 即 ~2 chars / token (中文 + LaTeX + markdown 混合)
CHARS_PER_TOKEN_ESTIMATE = 2.0

# 除 sentence pack 外的 prompt 常量开销 (system prompt + template 骨架 + fixed sections)
PROMPT_OVERHEAD_CHARS = 4_500      # 估: system_prompt ~500 + user template ~4000

# 每篇预计输出 tokens (v03 平均 ~1500-2500)
EXPECTED_OUTPUT_TOKENS_PER_CALL = 2_500

# 重试概率 (spec 七: 10% 重试预算; 最坏情况 100%)
DEFAULT_RETRY_RATE = 0.10


def estimate_tokens_from_chars(char_count: int) -> int:
    """char-based token 估算. 保守偏高."""
    return int(char_count / CHARS_PER_TOKEN_ESTIMATE + 0.5)


def route_to_tier(input_tokens: int) -> str:
    """按 moonshot-v1-auto 路由规则: 找第一个能装下的 tier."""
    for model, cap in TIER_THRESHOLDS:
        if input_tokens <= cap:
            return model
    return "moonshot-v1-128k"


def per_paper_cost_estimate(input_tokens: int,
                              output_tokens: int = EXPECTED_OUTPUT_TOKENS_PER_CALL,
                              tier: str = None) -> dict:
    """给定一篇 input+output tokens, 计算路由 + 单篇费用."""
    tier = tier or route_to_tier(input_tokens)
    price = MOONSHOT_PRICING_CNY_PER_M.get(tier,
                                            MOONSHOT_PRICING_CNY_PER_M["moonshot-v1-32k"])
    cost = (input_tokens / 1_000_000 * price["input"]
            + output_tokens / 1_000_000 * price["output"])
    return {
        "tier": tier,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_cny": round(cost, 6),
        "pricing_input_cny_per_m": price["input"],
        "pricing_output_cny_per_m": price["output"],
    }


# ---- Empirical linear from v03 baseline ----

V03_BASELINE = {
    "n_papers": 10,
    "total_calls": 10,     # all primary, no retries
    "total_tokens": 115_642,
    "total_cost_cny_recorded": 2.775,   # from v03 driver report
    "note": (
        "v03 driver 用 moonshot-v1-auto, 全部 primary, 0 重试. "
        "记录的费用假设 32k tier 单价. 实际账单可能略不同."
    ),
}


def empirical_linear_337(baseline: dict = None) -> dict:
    """从 v03 10 篇线性外推到 337 篇 (每篇 1 主 + 无重试)."""
    b = baseline or V03_BASELINE
    per_paper_cost = b["total_cost_cny_recorded"] / b["n_papers"]
    per_paper_tokens = b["total_tokens"] / b["n_papers"]
    per_paper_calls = b["total_calls"] / b["n_papers"]

    total_papers = 337
    total_cost = per_paper_cost * total_papers
    total_tokens = per_paper_tokens * total_papers
    total_calls = per_paper_calls * total_papers

    return {
        "method": "empirical_linear_from_v03",
        "n_papers": total_papers,
        "estimated_total_calls": round(total_calls),
        "estimated_total_tokens": round(total_tokens),
        "estimated_total_cost_cny": round(total_cost, 3),
        "baseline_source": b,
    }


# ---- per_token_actual: 基于每篇实际 sentence pack size ----

def per_token_actual_337(per_paper_char_counts: list,
                          retry_rate: float = DEFAULT_RETRY_RATE) -> dict:
    """基于每篇 sentence pack + prompt overhead 计算实际 tokens 估算.

    Args:
      per_paper_char_counts: list of int, 每篇的 sentence pack + overhead 字符数
      retry_rate: 假设的重试比例
    """
    tiers = {"moonshot-v1-8k": 0, "moonshot-v1-32k": 0, "moonshot-v1-128k": 0}
    total_input = 0
    total_output = 0
    total_cost = 0.0
    per_paper_details = []

    for ch in per_paper_char_counts:
        input_tokens = estimate_tokens_from_chars(ch)
        est = per_paper_cost_estimate(input_tokens,
                                       EXPECTED_OUTPUT_TOKENS_PER_CALL)
        tiers[est["tier"]] = tiers.get(est["tier"], 0) + 1
        total_input += input_tokens
        total_output += EXPECTED_OUTPUT_TOKENS_PER_CALL
        total_cost += est["cost_cny"]
        per_paper_details.append(est)

    total_calls_primary = len(per_paper_char_counts)
    retry_calls = int(round(total_calls_primary * retry_rate))
    retry_cost = total_cost * retry_rate

    return {
        "method": "per_token_actual",
        "n_papers": len(per_paper_char_counts),
        "estimated_total_calls_primary": total_calls_primary,
        "estimated_retry_calls_at_default_rate": retry_calls,
        "estimated_input_tokens": total_input,
        "estimated_output_tokens": total_output,
        "estimated_primary_cost_cny": round(total_cost, 3),
        "estimated_retry_cost_at_default_rate_cny": round(retry_cost, 3),
        "estimated_total_cost_cny": round(total_cost + retry_cost, 3),
        "papers_by_tier": tiers,
        "retry_rate_used": retry_rate,
        "assumed_output_tokens_per_call": EXPECTED_OUTPUT_TOKENS_PER_CALL,
        "chars_per_token_ratio": CHARS_PER_TOKEN_ESTIMATE,
    }


# ---- worst_case: 全 128k tier + 全部重试 ----

def worst_case_337(per_paper_char_counts: list) -> dict:
    """理论上限: 假设所有输入都被路由到 128k tier + 全部重试一次."""
    price = MOONSHOT_PRICING_CNY_PER_M["moonshot-v1-128k"]
    total_input = 0
    total_output = 0
    total_cost = 0.0
    for ch in per_paper_char_counts:
        input_tokens = estimate_tokens_from_chars(ch)
        out_tokens = EXPECTED_OUTPUT_TOKENS_PER_CALL
        cost = (input_tokens / 1_000_000 * price["input"]
                + out_tokens / 1_000_000 * price["output"])
        total_input += input_tokens
        total_output += out_tokens
        total_cost += cost

    # 全部重试
    total_input *= 2
    total_output *= 2
    total_cost *= 2

    return {
        "method": "worst_case_128k_and_full_retry",
        "n_papers": len(per_paper_char_counts),
        "estimated_total_calls": 2 * len(per_paper_char_counts),
        "estimated_input_tokens": total_input,
        "estimated_output_tokens": total_output,
        "estimated_total_cost_cny": round(total_cost, 3),
        "tier_used": "moonshot-v1-128k (assumed)",
    }


# ---- 组合报告 ----

def build_budget_report(per_paper_char_counts: list,
                          n_papers: int = 337,
                          batch_size: int = 25,
                          retry_rate: float = DEFAULT_RETRY_RATE,
                          model: str = DEFAULT_MODEL) -> dict:
    """综合三估算 + 批次划分."""
    n_batches = (n_papers + batch_size - 1) // batch_size

    tier_dist = {"moonshot-v1-8k": 0, "moonshot-v1-32k": 0,
                  "moonshot-v1-128k": 0}
    for ch in per_paper_char_counts:
        tk = estimate_tokens_from_chars(ch)
        tier_dist[route_to_tier(tk)] += 1

    # 超长论文 (> 128k tokens input) 清单
    over_128k = [
        i for i, ch in enumerate(per_paper_char_counts)
        if estimate_tokens_from_chars(ch) > 128_000
    ]

    return {
        "run_config": {
            "model_configured_as": model,
            "batch_size": batch_size,
            "n_batches": n_batches,
            "n_papers": n_papers,
            "retry_rate": retry_rate,
            "pricing_source": (
                "Moonshot 官网公开单价 (2024-2025). "
                "本估算全部标记为 'estimated_price'; 实际付费按官方账单."
            ),
            "chars_per_token_ratio": CHARS_PER_TOKEN_ESTIMATE,
            "expected_output_tokens_per_call": EXPECTED_OUTPUT_TOKENS_PER_CALL,
            "prompt_overhead_chars": PROMPT_OVERHEAD_CHARS,
        },
        "estimates": {
            "empirical_linear_from_v03": empirical_linear_337(),
            "per_token_actual": per_token_actual_337(per_paper_char_counts,
                                                        retry_rate),
            "worst_case_128k_full_retry": worst_case_337(per_paper_char_counts),
        },
        "tier_routing_distribution": tier_dist,
        "papers_over_128k_tokens": over_128k,
        "n_papers_over_128k": len(over_128k),
    }
