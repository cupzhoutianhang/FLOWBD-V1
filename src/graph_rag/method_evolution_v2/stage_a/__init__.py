"""Stage A — 方法节点抽取(纯抽取, 不做演化关系).

模块:
  - prompts:              LLM 抽取的 system / user 模板
  - llm_client:           Moonshot(Kimi) HTTP 客户端, 只从 MOONSHOT_API_KEY 环境变量读 key
  - evidence_validation:  抽取结果的本地证据校验(定位 evidence_quote)
  - method_extraction:    单篇论文抽取的编排

对外只公开 extract_paper 与 STAGE_A_VERSION.
"""
from method_evolution_v2.stage_a.method_extraction import (   # noqa: F401
    STAGE_A_VERSION,
    extract_paper,
)
