"""Render authoritative lineage fields directly, without inventing extra edges/authors."""
import re


def lineage_requested(question):
    """Reserve direct audit-table answers for explicit lineage requests.

    A generic substitution question, such as SOC replacing efficiency data, must
    remain on the ordinary evidence-answering path.
    """
    return bool(re.search(r"(?<![A-Z])(?:EXTENDS|IMPROVES|ADAPTS|REPLACES)(?![A-Z])", question.upper())
                or any(word in question for word in ("谱系", "演化", "借鉴")))


def render_lineage_answer(question, sources):
    requested = set(re.findall(r"(?<![A-Z])(?:EXTENDS|IMPROVES|ADAPTS|REPLACES)(?![A-Z])", question.upper()))
    if not lineage_requested(question):
        return None
    records, scope_ref = [], None
    for source in sources:
        if source.get("type") != "lineage":
            continue
        if source.get("doc_id") == "AUDIT:SCOPE":
            scope_ref = source["ref_id"]
        for chunk in source.get("chunks") or [source]:
            record = chunk.get("audit_record")
            if record:
                records.append((source["ref_id"], record))
    if not records:
        return None
    selected = records
    if "之外" in question and "扩散" in question:
        selected = [(ref, r) for ref, r in selected if "扩散" not in r["edge"]["from_method_name"] + r["edge"]["to_method_name"]]
    if requested:
        selected = [(ref, r) for ref, r in selected if r["edge"]["relation"] in requested]
    if "confirmed" in question.lower():
        selected = [(ref, r) for ref, r in selected if r["confirmed_records"]]
    lines = []
    if not selected:
        lines.append("本次权威谱系查询没有记录符合所问类型和方法范围的关系；不能据此编造替代或借鉴边。")
        lines.append("相关的已记录关系如下：")
        selected = records
    else:
        lines.append(f"在本次查询的人工校正谱系中，符合问题范围的关系有 {len(selected)} 条：")
    for ref, record in selected:
        row = record["edge"]
        status = "人工校正 accepted"
        if record["confirmed_records"]:
            status += "；同一证据有正式 confirmed 文件记录，按一条关系计数"
        lines.append(f"\n- **{row['relation']}**：{row['from_method_name']} → {row['to_method_name']}。状态：{status}。[Ref-{ref}]"
                     f"\n  证据句编号：{row['relation_evidence_sentence_ids']}。"
                     f"\n  数据方向依据：{row['direction_basis']}。[Ref-{ref}]")
        lines.append(f"  适用范围：{row['data_boundary']}。[Ref-{ref}]")
    lines.append("\n箭头遵循数据表的方向：借鉴者/扩展者/改进方/新体系 → 来源/被改进方/被替代体系；展示图按旧→新绘制时可能反向。")
    if scope_ref:
        lines.append(f"\n查询边界：人工校正的五条案例及其中 ADAPTS 对应的正式 confirmed 记录；其余 accepted 案例不升级为 confirmed。未记录不等于所有文献中不存在。[Ref-{scope_ref}]")
    return "\n".join(lines)
