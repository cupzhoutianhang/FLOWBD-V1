"""
fix_peripheral.py — 修正 87 个 peripheral 节点里的误抓 (阶段 B 补丁)

规则:
  - 强匹配词命中 name/innovation -> 真超疏水, 保留 peripheral=True
  - 都不命中 -> 误抓:
      peripheral=False
      cluster_id=-1 (归噪声)
      reclassified_from_peripheral=True (审计痕迹)
      secondary_topic = 按 Part 2 的 17 个子主题关键词重新匹配, 匹配不上则空

只改属性, 不动 UMAP 坐标. 直接在 Neo4j 上 SET.
"""
from __future__ import annotations

import sys

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = __import__("os").environ.get("NEO4J_PASSWORD", "")

# 强匹配词 (命中即真超疏水/油水分离)
HYDRO_KEYWORDS = [
    "超疏水", "超疏油", "超亲水", "油水分离", "疏液", "疏油", "油-水", "水油", "防水涂层",
    "superhydrophobic", "superoleophobic", "oil-water", "hydrophobic coating",
    "疏水涂层", "双疏", "亲气",
]

# Part 2 的 13 个可用子主题 -> 关键词 (给误抓节点重新分配 secondary_topic)
SECONDARY_KEYWORDS = {
    "Ni 基电极 (Ni3S2/泡沫镍)": ["ni3s2", "泡沫镍", "nico2o4", "氢氧化镍", "ni-co", "镍钴", "镍基"],
    "PANI 聚苯胺纳米阵列": ["pani", "聚苯胺", "聚吡咯", "ppy"],
    "相变微胶囊封装": ["微胶囊", "原位聚合", "复凝聚", "壁材"],
    "物理储能 CAES/LAES": ["caes", "压缩空气", "液态空气", "laes", "液氢", "lng冷能", "超临界co"],
    "石蜡复合 PCM": ["石蜡", "膨胀石墨", "脂肪酸", "硬脂酸", "癸酸", "月桂酸", "棕榈酸", "相变材料"],
    "静电纺丝碳纳米纤维": ["静电纺丝", "纺丝", "碳纳米纤维"],
    "锂电池家族 (锂硫/锂氧/锂离子电容器)": ["锂硫", "锂氧", "锂-二氧化碳", "锂二氧化碳", "锂离子电容器", "金属锂"],
    "电池管理 BMS / 故障诊断": ["故障诊断", "soc", "短路检测", "电池一致性", "电池包", "电池管理"],
    "能源系统集成": ["电-氢", "电氢", "风光制氢", "退役电池", "容量配置", "光储充", "氢储能", "电转气"],
    "离子交换膜 (Nafion/SPEEK)": ["nafion", "speek", "spsf", "全氟磺酸", "磺化聚芳醚", "质子交换膜", "离子选择"],
    "制氢/电解水/电转气": ["电解水", "甲烷化", "甲烷重整", "co2还原", "碱性电解", "pem电解"],
    "多孔碳模板法": ["软模板", "硬模板", "f127", "pmma模板", "活性炭", "活化炭", "多孔碳"],
    "生物质热解碳化": ["生物质", "木质素", "纤维素衍生", "果壳", "松花粉", "甘蔗渣", "稻壳", "碳化"],
}


def is_real_hydrophobic(text: str) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in HYDRO_KEYWORDS)


def guess_secondary(text: str) -> str:
    t = text.lower()
    best = ("", 0)
    for topic, kws in SECONDARY_KEYWORDS.items():
        score = sum(t.count(kw.lower()) for kw in kws)
        if score > best[1]:
            best = (topic, score)
    return best[0]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    from neo4j import GraphDatabase, basic_auth

    driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PWD))
    real_peri = []
    wrong_peri = []
    try:
        with driver.session() as session:
            # 拉所有 peripheral 节点
            rows = session.run(
                "MATCH (m:ProposedMethod {peripheral: true}) "
                "RETURN m.paper_id AS pid, m.name AS name, "
                "coalesce(m.innovation,'') AS inno"
            ).data()
            print(f"[scan] peripheral 节点: {len(rows)}")

            for row in rows:
                text = f"{row['name']} {row['inno']}"
                if is_real_hydrophobic(text):
                    real_peri.append(row)
                else:
                    sec = guess_secondary(text)
                    wrong_peri.append({**row, "new_secondary": sec})

            print(f"[scan] 真超疏水: {len(real_peri)}  | 误抓: {len(wrong_peri)}")

            # 更新误抓节点
            print(f"[update] 修正 {len(wrong_peri)} 个误抓节点...")
            for w in wrong_peri:
                session.run(
                    """
                    MATCH (m:ProposedMethod {paper_id: $pid, name: $name})
                    SET m.peripheral = false,
                        m.cluster_id = -1,
                        m.cluster_label = '未归类',
                        m.reclassified_from_peripheral = true,
                        m.secondary_topic = $sec
                    """,
                    pid=w["pid"], name=w["name"], sec=w["new_secondary"],
                ).consume()

            # 验证
            print("\n[verify] 修正后计数:")
            r = session.run(
                "MATCH (m:ProposedMethod {peripheral: true}) RETURN count(m) AS c"
            ).single()
            print(f"  仍 peripheral=True: {r['c']}")
            r = session.run(
                "MATCH (m:ProposedMethod {reclassified_from_peripheral: true}) "
                "RETURN count(m) AS c"
            ).single()
            print(f"  reclassified_from_peripheral=True: {r['c']}")
            r = session.run(
                "MATCH (m:ProposedMethod {reclassified_from_peripheral: true}) "
                "WHERE m.secondary_topic <> '' "
                "RETURN count(m) AS c"
            ).single()
            print(f"    其中重新分配到 secondary_topic 的: {r['c']}")

    finally:
        driver.close()

    # 报告
    print("\n========== 报告 ==========")
    print(f"真超疏水节点: {len(real_peri)}")
    print(f"误抓节点:     {len(wrong_peri)}")
    print(f"\n真超疏水示例 5 条:")
    for r in real_peri[:5]:
        print(f"  - {r['name'][:55]}")
    print(f"\n误抓节点示例 5 条 (+ 重新分配的 secondary_topic):")
    for w in wrong_peri[:5]:
        sec = w["new_secondary"] or "(无匹配, 留空)"
        print(f"  - {w['name'][:50]}")
        print(f"      -> secondary_topic: {sec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
