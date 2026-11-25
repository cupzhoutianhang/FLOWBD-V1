"""
embed_methods.py — 用本地 bge-m3 给所有方法节点做 embedding (阶段 B Step 2)

输入  : method_outputs/*.json
输出  : landscape/embeddings.pkl
        含 {ids, texts, embeddings(np.ndarray, normalized)}
        ids 是 (paper_id, method_name) 元组列表
模型  : src/rag/models/bge-m3 (本地, 不重新下)
策略  : own_method  -> name + 创新点 + 解决问题  (信息丰富)
        ref_method  -> name                     (信息有限)
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time

# 必须在 import transformers 之前: 禁掉 TF/Flax backend,
# 避免 Keras 3 / Transformers 兼容问题
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ME_DIR = os.path.dirname(THIS_DIR)  # method_extraction
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ME_DIR)))  # 仓库根
METHOD_OUT = os.path.join(ME_DIR, "method_outputs")
BGE_M3_PATH = os.path.join(PROJECT_ROOT, "src", "rag", "models", "bge-m3")
OUTPUT_PKL = os.path.join(THIS_DIR, "embeddings.pkl")

# 单条文本最大字符 (bge-m3 max_seq=8192, 我们用 600 字符够包含 name+inno+prob)
MAX_TEXT_CHARS = 600
BATCH_SIZE = 32


def _build_text(kind: str, m: dict) -> str:
    """生成给 bge-m3 的输入文本.
    own: name + 创新点 + 解决问题; ref: name only."""
    name = (m.get("name") or "").strip()
    if kind == "own":
        parts = [name]
        inno = (m.get("innovation") or "").strip()
        prob = (m.get("problem_solved") or "").strip()
        if inno:
            parts.append(f"创新点: {inno}")
        if prob:
            parts.append(f"解决问题: {prob}")
        text = "。".join(parts)
    else:
        text = name
    return text[:MAX_TEXT_CHARS]


def collect_methods() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """遍历所有 paper JSON, 收集 (paper_id, name) -> text 映射.
    返回 (ids, texts, kinds)."""
    ids: list[tuple[str, str]] = []
    texts: list[str] = []
    kinds: list[str] = []
    seen: set[tuple[str, str]] = set()

    for fn in sorted(os.listdir(METHOD_OUT)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(METHOD_OUT, fn), "r", encoding="utf-8") as f:
            d = json.load(f)
        pid = d.get("paper_id", "")
        for kind, list_key in (("own", "own_methods"), ("ref", "referenced_methods")):
            for m in d.get(list_key, []) or []:
                name = (m.get("name") or "").strip()
                if not name:
                    continue
                key = (pid, name)
                if key in seen:
                    continue
                seen.add(key)
                ids.append(key)
                texts.append(_build_text(kind, m))
                kinds.append(kind)
    return ids, texts, kinds


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if not os.path.isdir(BGE_M3_PATH):
        print(f"[ERR] bge-m3 路径不存在: {BGE_M3_PATH}", file=sys.stderr)
        return 1

    print("[1/4] 收集方法节点...")
    ids, texts, kinds = collect_methods()
    n_own = sum(1 for k in kinds if k == "own")
    n_ref = sum(1 for k in kinds if k == "ref")
    print(f"      共 {len(ids)} 个 (own={n_own}, ref={n_ref})")

    print("[2/4] 加载 bge-m3 (transformers 直调, 绕开 sentence-transformers)...")
    import torch
    import torch.nn.functional as F
    from transformers import AutoModel, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"      device = {device}")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(BGE_M3_PATH)
    model = AutoModel.from_pretrained(BGE_M3_PATH).to(device)
    model.eval()
    print(f"      模型加载用时 {time.time()-t0:.1f}s")

    print(f"[3/4] 向量化 {len(texts)} 条 (batch={BATCH_SIZE}, CLS pooling + L2 normalize)...")

    @torch.no_grad()
    def _encode_batch(batch_texts: list[str]):
        enc = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(device)
        out = model(**enc)
        # bge-m3 标准: [CLS] token (位置 0) + L2 normalize
        cls = out.last_hidden_state[:, 0]
        return F.normalize(cls, p=2, dim=1).cpu().numpy()

    import numpy as np

    t0 = time.time()
    chunks = []
    for i in range(0, len(texts), BATCH_SIZE):
        chunk = _encode_batch(texts[i : i + BATCH_SIZE])
        chunks.append(chunk)
        if (i // BATCH_SIZE) % 5 == 0:
            print(f"        ... {i + len(chunk)}/{len(texts)}")
    embeddings = np.vstack(chunks)
    print(f"      shape = {embeddings.shape}  用时 {time.time()-t0:.1f}s")

    print(f"[4/4] 写入 {OUTPUT_PKL}")
    with open(OUTPUT_PKL, "wb") as f:
        pickle.dump(
            {"ids": ids, "texts": texts, "kinds": kinds, "embeddings": embeddings},
            f,
        )

    print("\n[done] embedding 完成")
    print(f"  文件: {OUTPUT_PKL}")
    print(f"  大小: {os.path.getsize(OUTPUT_PKL) / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
