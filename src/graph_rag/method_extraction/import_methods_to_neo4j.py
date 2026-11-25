"""
import_methods_to_neo4j.py — 把 method_outputs/*.json 导入 Neo4j

不动现有图谱! 只 CREATE/MERGE 自己的命名空间:
  节点: :ProposedMethod {paper_id, name, year, innovation, problem_solved,
                         components, source, citation_clue}
  关系: -[:METHOD_EXTENDS|METHOD_IMPROVES|METHOD_ADAPTS|METHOD_REPLACES
         {confidence, evidence, reason, from_paper}]->
  注: 关系名加 METHOD_ 前缀是因为老图谱已用 IMPROVES (Material->Property 之类),
      加前缀彻底隔离, 不会撞.

唯一键: (paper_id, name)  -> 同一篇里同名方法去重; 跨篇同名是不同节点
        (跨篇方法的真正去重在阶段 B 的 embedding 去重做)

用法:
  python import_methods_to_neo4j.py                # 导入 method_outputs/ 全部
  python import_methods_to_neo4j.py --dry-run      # 只打印, 不写库
  python import_methods_to_neo4j.py --clear        # 先清空 :ProposedMethod 命名空间再导
  python import_methods_to_neo4j.py --uri bolt://localhost:7687 --pwd neo4j123
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(THIS_DIR, "method_outputs")

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PWD = __import__("os").environ.get("NEO4J_PASSWORD", "")

# LLM 输出的关系名 (不带前缀)
LLM_RELATIONS = {"EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"}
# 写入 Neo4j 时一律加 METHOD_ 前缀, 避开老图谱已有的 IMPROVES 等关系名
NEO4J_REL_PREFIX = "METHOD_"
NEO4J_RELS_PATTERN = "|".join(f"{NEO4J_REL_PREFIX}{r}" for r in LLM_RELATIONS)


def load_records() -> list[dict]:
    out = []
    for fn in sorted(os.listdir(OUTPUT_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(OUTPUT_DIR, fn), "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [skip] {fn}: {exc}", file=sys.stderr)
    return out


def _flatten_method(paper_id: str, year, kind: str, m: dict) -> dict:
    """own / referenced method -> 统一节点 props.
    kind = 'own' or 'ref'."""
    return {
        "paper_id": paper_id,
        "name": m.get("name", "").strip(),
        "year": year,
        "innovation": m.get("innovation", "") if kind == "own" else "",
        "problem_solved": m.get("problem_solved", "") if kind == "own" else "",
        "components": " | ".join(m.get("key_components", []) or []) if kind == "own" else "",
        "source": kind,  # 'own' or 'ref'
        "citation_clue": m.get("citation_clue", "") if kind == "ref" else "",
    }


def collect_nodes_and_edges(records: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """从 records 抽出待写入的节点和边. 同时返回统计字典."""
    nodes: list[dict] = []
    edges: list[dict] = []
    stats = Counter()

    # paper_id+name 去重 (同一篇内同名方法)
    seen: set[tuple[str, str]] = set()

    for d in records:
        paper_id = d.get("paper_id", "")
        year = d.get("year")  # already int or None
        stats["papers"] += 1

        for m in d.get("own_methods", []) or []:
            name = m.get("name", "").strip()
            if not name:
                stats["skip_no_name"] += 1
                continue
            key = (paper_id, name)
            if key in seen:
                stats["dup_in_paper"] += 1
                continue
            seen.add(key)
            nodes.append(_flatten_method(paper_id, year, "own", m))
            stats["own_methods"] += 1

        for m in d.get("referenced_methods", []) or []:
            name = m.get("name", "").strip()
            if not name:
                stats["skip_no_name"] += 1
                continue
            key = (paper_id, name)
            if key in seen:
                stats["dup_in_paper"] += 1
                continue
            seen.add(key)
            nodes.append(_flatten_method(paper_id, year, "ref", m))
            stats["ref_methods"] += 1

        for e in d.get("evolution_edges", []) or []:
            rel = (e.get("relation", "") or "").upper().strip()
            if rel not in LLM_RELATIONS:
                stats[f"bad_relation_{rel or 'EMPTY'}"] += 1
                continue
            fm = (e.get("from_method") or "").strip()
            tm = (e.get("to_method") or "").strip()
            if not fm or not tm:
                stats["skip_edge_no_name"] += 1
                continue
            edges.append(
                {
                    "from_paper": paper_id,
                    "from_method": fm,
                    "to_method": tm,
                    "relation": rel,
                    "confidence": (e.get("confidence") or "").lower(),
                    "evidence": (e.get("evidence") or "")[:500],
                    "reason": (e.get("reason") or "")[:500],
                }
            )
            stats[f"edge_{rel}"] += 1

    return nodes, edges, stats


# ---------- Cypher 模板 ----------
CYPHER_CLEAR_NODES = """
MATCH (n:ProposedMethod) DETACH DELETE n
"""

CYPHER_MERGE_NODE = """
MERGE (m:ProposedMethod {paper_id: $paper_id, name: $name})
SET m.year = $year,
    m.source = $source,
    m.innovation = $innovation,
    m.problem_solved = $problem_solved,
    m.components = $components,
    m.citation_clue = $citation_clue
"""

# 关系: 在同一篇 paper 内, 把 from_method/to_method 解析为节点然后建关系
# 注意: from_method/to_method 必须能在该 paper 的 ProposedMethod 节点里找到 (按 name)
# 如果找不到 (LLM 边里的方法名和节点列表里的对不上), 自动创建一个 source='auto' 的节点占位
CYPHER_CREATE_EDGE = """
MATCH (src:ProposedMethod {paper_id: $from_paper, name: $from_method})
MATCH (dst:ProposedMethod {paper_id: $from_paper, name: $to_method})
MERGE (src)-[r:%s]->(dst)
SET r.confidence = $confidence,
    r.evidence = $evidence,
    r.reason = $reason,
    r.from_paper = $from_paper
"""

# 容错: 边里的方法名找不到时, 自动建占位节点
CYPHER_ENSURE_NODE = """
MERGE (m:ProposedMethod {paper_id: $paper_id, name: $name})
ON CREATE SET m.source = 'auto_from_edge', m.year = $year
"""


def execute_import(
    nodes: list[dict],
    edges: list[dict],
    uri: str,
    user: str,
    pwd: str,
    clear: bool,
    dry_run: bool,
) -> dict:
    """返回执行统计."""
    stats = Counter()

    if dry_run:
        print(f"\n[DRY-RUN] 不连接数据库. 将会:")
        print(f"  - {'清空 :ProposedMethod 命名空间' if clear else '保留现有 :ProposedMethod 节点'}")
        print(f"  - MERGE {len(nodes)} 个节点")
        print(f"  - MERGE {len(edges)} 条关系")
        stats["dry_run"] = 1
        return stats

    from neo4j import GraphDatabase, basic_auth  # noqa: WPS433

    driver = GraphDatabase.driver(uri, auth=basic_auth(user, pwd))
    try:
        # 联通性测试
        with driver.session() as session:
            session.run("RETURN 1").consume()
        print(f"[neo4j] 已连接 {uri}")

        with driver.session() as session:
            if clear:
                print("[clear] 删除 :ProposedMethod 命名空间下所有节点和关系...")
                session.run(CYPHER_CLEAR_NODES).consume()
                stats["cleared"] = 1

            # 1. 节点
            print(f"[nodes] 写入 {len(nodes)} 个节点...")
            for n in nodes:
                session.run(CYPHER_MERGE_NODE, **n)
                stats["nodes_written"] += 1

            # 2. 边 (按 relation 类型分组, 每组用一个 Cypher 模板)
            print(f"[edges] 写入 {len(edges)} 条关系...")
            paper_id_to_year: dict[str, Any] = {
                n["paper_id"]: n["year"] for n in nodes
            }
            for e in edges:
                # 容错: 确保 from / to 节点存在
                year = paper_id_to_year.get(e["from_paper"])
                session.run(
                    CYPHER_ENSURE_NODE,
                    paper_id=e["from_paper"],
                    name=e["from_method"],
                    year=year,
                ).consume()
                session.run(
                    CYPHER_ENSURE_NODE,
                    paper_id=e["from_paper"],
                    name=e["to_method"],
                    year=year,
                ).consume()
                rel_full = f"{NEO4J_REL_PREFIX}{e['relation']}"  # METHOD_EXTENDS etc.
                cypher = CYPHER_CREATE_EDGE % rel_full
                session.run(cypher, **e).consume()
                stats[f"edge_{rel_full}"] += 1

            # 3. 验证统计 (只看 METHOD_ 前缀的关系, 老图谱关系不计)
            r1 = session.run(
                "MATCH (m:ProposedMethod) RETURN count(m) AS c"
            ).single()
            r2 = session.run(
                f"MATCH (a:ProposedMethod)-[r:{NEO4J_RELS_PATTERN}]->(b:ProposedMethod) "
                "RETURN count(r) AS c"
            ).single()
            stats["neo4j_node_count"] = r1["c"]
            stats["neo4j_edge_count"] = r2["c"]
    finally:
        driver.close()

    return stats


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default=DEFAULT_URI)
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--pwd", default=DEFAULT_PWD)
    ap.add_argument("--clear", action="store_true",
                    help="先清空 :ProposedMethod 命名空间. 不影响其他标签节点!")
    ap.add_argument("--dry-run", action="store_true",
                    help="只解析 JSON 不连数据库, 报告会写入多少节点/边")
    args = ap.parse_args()

    if not os.path.isdir(OUTPUT_DIR):
        print(f"[ERR] {OUTPUT_DIR} 不存在", file=sys.stderr)
        return 1

    records = load_records()
    print(f"[init] 加载 {len(records)} 篇 method JSON")

    nodes, edges, parse_stats = collect_nodes_and_edges(records)
    print(f"[parse] 节点 {len(nodes)} 个, 边 {len(edges)} 条")
    print(f"        parse 详细: {dict(parse_stats)}")

    exec_stats = execute_import(
        nodes, edges,
        uri=args.uri, user=args.user, pwd=args.pwd,
        clear=args.clear, dry_run=args.dry_run,
    )

    print(f"\n[done] {dict(exec_stats)}")
    if not args.dry_run:
        print()
        print("Neo4j Browser 验证 (复制到 http://localhost:7474):")
        print("  MATCH (m:ProposedMethod) RETURN count(m)")
        print(f"  MATCH ()-[r:{NEO4J_RELS_PATTERN}]->() RETURN type(r), count(r)")
        print("  MATCH p=(:ProposedMethod)-[:METHOD_EXTENDS]->(:ProposedMethod) RETURN p LIMIT 25")
    return 0


if __name__ == "__main__":
    sys.exit(main())
