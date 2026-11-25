# 节点表 schema（nodes.csv · 统一 30 字段）

> 适用于三个案例统一目录 `paper/lineage_cases_unified/<case_id>/nodes.csv`。
> 编码 **UTF-8 with BOM**（Excel 直接打开中文不乱码）。所有案例列名、列序、含义完全一致；
> 某案例缺某类信息时**留空**，**不得删列**。

## 字段定义（严格按此顺序）

| # | 字段 | 类型 | 说明 |
|---|---|---|---|
| 1 | `case_id` | enum | `pcm_stability` / `co_co2_hydrogenation` / `aorfb_active_materials` |
| 2 | `node_id` | str | 案例内唯一节点号（PCM=P01..、CO=N01..、AORFB=N00/A0x/B0x..，沿用原案例编号，不重排） |
| 3 | `node_name` | str | 纯文本可检索名（**无 Unicode 上下标**，用于全文检索/去重/前端搜索） |
| 4 | `display_name` | str | 展示名（**可含 Unicode 下标**，如 `Br₂`、`K₄Fe(CN)₆`；用于论文排版/前端标签） |
| 5 | `year` | str | 年份（纯数字或区间如 `2005–2007`；不可考则留空，**不补造**） |
| 6 | `year_label` | str | 年份轴显示文本（可为 `传统基线`/`无机基线` 等非数字锚点） |
| 7 | `year_source` | enum | `in_corpus_primary`（语料内一次论文直接给出）/ `review_cited`（综述/引言转引）/ `unknown` |
| 8 | `branch_id` | str | 分支机读键（如 `diffusion`/`weighing`/`SiO2壳`/`A`/`B`；细粒度） |
| 9 | `branch_name` | str | 分支中文名（前端泳道标题用） |
| 10 | `node_type` | enum | 主图着色键：`baseline` / `track_primary` / `track_secondary` / `track_tertiary` / `track_quaternary` / `auxiliary_c..f`（详见 `visual_style_guide.md`） |
| 11 | `node_color` | hex | 该节点填充色（与 node_type 对应，冗余存储便于前端直读） |
| 12 | `source_paper` | str | 来源论文题名/缩写（综述转引者为被引一次文献；不在语料内者照录） |
| 13 | `source_authors` | str | 作者（原文可得则录，**缺失留空不补造**） |
| 14 | `source_journal` | str | 期刊/出处（同上） |
| 15 | `doi_or_reference` | str | DOI 或综述内参考文献编号（如 `[21]`；无则留空） |
| 16 | `source_scope` | enum | `in_corpus_primary`（语料内一次论文）/ `in_corpus_review`（语料内综述本身）/ `review_cited_external`（综述转引、原文不在语料内） |
| 17 | `method_or_material` | str | 方法名 / 材料名（案例主体对象） |
| 18 | `composition_or_structure` | str | 组成/结构（催化剂壳层、分子官能团、配方等；无则留空） |
| 19 | `research_object` | str | 研究对象/体系 |
| 20 | `target_or_product` | str | 目标/产物（如目标产物、正负极对、评价目标） |
| 21 | `problem_solved` | str | 相对上一代解决的问题（原文有则录，无则留空） |
| 22 | `key_performance` | str | 关键性能指标（**原样照录数字与单位，不折算、不补造**；无则留空或 `—`） |
| 23 | `evidence_sentence` | str | **原文证据句（逐字保留，禁止改写/断句/补全）** |
| 24 | `evidence_location` | str | 证据定位（§章节 / 行号 / 段句号，如 `S1 §2.1 line99` / `introduction_p8_s5`） |
| 25 | `sentence_id` | str | 证据句机读 id（如 `s1_L99_s3`；无则留空） |
| 26 | `evidence_level` | enum | `high` / `medium` / `low`（证据强度；medium 须在 notes 说明原因） |
| 27 | `verification_status` | enum | `in_corpus_verified` / `review_text_locatable` / `pending_primary_verification`（见下） |
| 28 | `main_figure` | bool | `true`/`false`：是否入选 8 节点主图 |
| 29 | `display_order` | int | 主图/前端展示排序（同分支内自旧到新） |
| 30 | `notes` | str | 备注（取舍理由、证据强度说明、订正记录等） |

## 枚举取值口径

**`source_scope`**
- `in_corpus_primary`：该节点来自**语料内一次论文**（可独立核验原文）。
- `in_corpus_review`：该节点即**语料内综述本身**（如 S1/S2）。
- `review_cited_external`：综述/引言**转引**的一次文献，**原文不在语料内**。

**`verification_status`**
- `in_corpus_verified`：语料内一次论文可直接核验（最强）。
- `review_text_locatable`：**两刊/主论文综述文本层面可定位**（证据句+定位齐备），**不代表独立复现核验**。
- `pending_primary_verification`：待核（仅有线索、定位不全）。

> **诚信红线**：`review_text_locatable` ≠ 对一次论文的独立核验。凡 `source_scope=review_cited_external` 的节点，其 `verification_status` 最高只能是 `review_text_locatable`。

## 校验规则（validate_all_cases.py 强制）
1. 30 字段齐全、列序一致、编码 UTF-8-BOM。
2. `node_id` 案例内唯一。
3. `node_type` ∈ 允许集；`node_color` 与 `node_type` 映射一致。
4. `source_scope=review_cited_external` ⇒ `verification_status ≠ in_corpus_verified`。
5. `main_figure=true` 的节点数 = 8（每案例）。
6. `evidence_level=medium/low` 时 `notes` 非空。
7. `year` 非空时为数字或 `dddd–dddd` 区间格式。
