# 关系表 schema（edges.csv · 统一 22 字段）

> 适用于 `paper/lineage_cases_unified/<case_id>/edges.csv`。编码 **UTF-8 with BOM**。
> **即使某案例没有某类关系，也保留统一表头，仅数据行为空**（如 PCM 无 baseline/route 边，
> edges.csv 仍含全部 22 列表头 + 1 行 direct_evolution）。

## 字段定义（严格按此顺序）

| # | 字段 | 类型 | 说明 |
|---|---|---|---|
| 1 | `case_id` | enum | 同 node_schema |
| 2 | `edge_id` | str | 案例内唯一边号（`PCM_E01` / `CO_E001` / `AO_E001`） |
| 3 | `source_id` | str | **旧节点** node_id（时间在前/被继承方） |
| 4 | `target_id` | str | **新节点** node_id（时间在后/继承方） |
| 5 | `source_name` | str | 旧节点展示名（冗余，便于直读） |
| 6 | `target_name` | str | 新节点展示名 |
| 7 | `relation_type` | enum | `ADAPTS`/`IMPROVES`/`EXTENDS`/`REPLACES`/`BASELINE_COMPARE`/`ROUTE_ASSOCIATION` |
| 8 | `relation_class` | enum | `direct_evolution`/`baseline_comparison`/`node_performance_comparison`/`route_association` |
| 9 | `line_style` | enum | `solid`/`dash_dot`/`dashed`（由 relation_class 决定，见下映射） |
| 10 | `line_color` | hex | 线色（由 relation_class 决定，见下映射） |
| 11 | `display_label` | str | 主图/前端边标签 |
| 12 | `evidence_sentence` | str | **原文证据句（逐字保留）** |
| 13 | `evidence_location` | str | 证据定位 |
| 14 | `sentence_id` | str | 证据句机读 id |
| 15 | `evidence_keyword` | str | 触发语关键词（如"在此基础上""相比前者…提升""取代"） |
| 16 | `evidence_level` | enum | `high`/`medium`/`low` |
| 17 | `verification_status` | enum | 同 node_schema |
| 18 | `main_figure` | bool | 是否为主图 8 节点子图内的边 |
| 19 | `display_order` | int | 展示排序 |
| 20 | `edge_scope` | enum | `dataset`＝语料核查候选边（默认）；`figure_only`＝仅为主图视觉连通而增设、不在原始候选边表内 |
| 21 | `count_in_dataset` | bool | 是否计入全量数据统计。`true`（默认）计入；`false`＝仅主图展示，不计入 direct/baseline/node_performance/route 全量统计 |
| 22 | `notes` | str | 备注（订正、强度、仅展示用连接线说明等） |

## ⚠️ 方向语义（前端务必按此解读，避免误读箭头）

**所有边一律 `source_id`=旧、`target_id`=新，箭头永远指向"新"（旧 → 新）。** 箭头方向 = 时间/演化方向，**与"谁改进谁"的主体无关**，各关系类型的主体如下：

| relation_type | 语义（箭头 旧→新） | 主体是谁 |
|---|---|---|
| `IMPROVES` | **新** 相对 **旧** 有改进/提升 | target 改进 source |
| `ADAPTS` | **新** 借鉴/迁移/母体改造自 **旧** | target 借鉴 source |
| `EXTENDS` | **新** 在 **旧** 基础上扩展 | target 扩展 source |
| `REPLACES` | **新** 取代 **旧** | target 取代 source |
| `BASELINE_COMPARE` | **新型材料/方法** 相对 **旧基线** 的性能对照 | target 对照 source(基线) |
| `ROUTE_ASSOCIATION` | 同一路线/家族的归类并列（**非事实继承**） | 无主体，仅归类 |

> 例：`A03 —IMPROVES→ A04` 读作"A04（新）相比 A03（旧）循环稳定性与开路电压提升"，
> **不是**"A03 改进了 A04"。前端渲染箭头 = 从 source 指向 target。

## relation_class → 线型/线色映射（三张图完全一致）

| relation_class | line_style | line_color | 计入"直接演化关系数"? |
|---|---|---|---|
| `direct_evolution` | `solid`（实线） | `#111827`（近黑） | ✅ 是 |
| `baseline_comparison` | `dash_dot`（点划线） | `#C65A00`（橙） | ❌ 否 |
| `node_performance_comparison` | `dash_dot`（点划线） | `#C65A00`（橙） | ❌ 否 |
| `route_association` | `dashed`（虚线） | `#71839B`（灰蓝） | ❌ 否 |

- `dash_dot` 在 Graphviz 中无原生支持：dot 先出 `dashed` 且打 `class="rel-basecmp"`，
  再由 `render_main_figure.py` 后处理把该组 `stroke-dasharray` 改写为 `8,3,1.5,3`（真点划线）。
- **只有 `direct_evolution` 计入"直接演化关系数"**；baseline/performance/route 均为对照或归类，不作事实继承关系。

## relation_type ↔ relation_class 约束
- `ADAPTS`/`EXTENDS`/`REPLACES` ⇒ `direct_evolution`
- `IMPROVES` ⇒ `direct_evolution`（有历史承接措辞：在此基础上/借鉴/进一步设计/替代等）
  **或** `node_performance_comparison`（证据仅为节点级性能倍数比较、无历史承接措辞，如 CO N38→N39"活性高 5～7 倍"）
- `BASELINE_COMPARE` ⇒ `baseline_comparison`（相对传统基线的性能对照）
- `ROUTE_ASSOCIATION` ⇒ `route_association`

> **`direct_evolution` 与 `node_performance_comparison` 的判据**：是否存在"历史承接措辞"。
> 有承接（如"在此基础上进一步设计""借鉴…改造"）⇒ `direct_evolution`（实线，计入直接演化）；
> 仅性能优劣的倍数/数值比较、无承接 ⇒ `node_performance_comparison`（点划线，**不**计入直接演化）。

## edge_scope / count_in_dataset 口径（区分语料核查边与仅展示连接）
- `edge_scope=dataset` 且 `count_in_dataset=true`（默认）：语料核查候选边，计入全量数据统计。
- `edge_scope=figure_only` 且 `count_in_dataset=false`：仅为主图视觉连通而增设的展示连接，**不在原始候选边表内**，
  **不计入**任何全量数据统计（direct/baseline/node_performance/route）；主图仍可显示以保证连通。
- **报告口径**：路线归类须分别列出"语料核查路线归类关系"（dataset）与"主图显示路线归类线 / 其中仅视觉连通展示线"（figure_only），
  **不得**把两者相加笼统写作一个总数。例：CO = **语料核查 21 条 + 主图展示连接 2 条**（N01→N29、N02→N55），不得写作"23 条"。

## 校验规则（validate_all_cases.py 强制）
1. 22 字段齐全、列序一致、编码 UTF-8-BOM（即使 0 数据行也保留表头）。
2. `source_id`/`target_id` 必须存在于本案例 nodes.csv。
3. `relation_type`↔`relation_class`↔`line_style`↔`line_color` 四者映射自洽（IMPROVES 允许 direct_evolution 或 node_performance_comparison）。
4. 各 relation_class 的 **dataset 口径**边数（count_in_dataset≠false）= manifest 对应计数（direct/baseline/node_performance/route）；figure_only 单列于 `route_figure_only_count`。
5. `main_figure=true` 的边全部落在 8 个 `main_figure=true` 节点之间。
6. `evidence_level≠high` 时 `notes` 说明原因。
7. 仅用于主图展示、不在原始候选边表内的连接线，须标 `edge_scope=figure_only`/`count_in_dataset=false` 并在 `notes` 显式标注（如 CO 的 N01→N29、N02→N55）。
8. `node_performance_comparison` 不计入 `direct_evolution_count`（C18）；`figure_only` 不计入全量统计（C19）；CO N38→N39 必须为点划线（C22）。
