# 案例清单 schema（case_manifest.json / all_cases_manifest.json）

> 每案例目录下 `case_manifest.json` 为该案例机读元数据；顶层 `all_cases_manifest.json`
> 为三案例聚合索引。编码 UTF-8（无 BOM，标准 JSON）。

## 顶层 `all_cases_manifest.json`

```jsonc
{
  "generated": "YYYY-MM-DD",
  "data_version": "1.0",
  "cases": [
    {
      "case_id": "pcm_stability|co_co2_hydrogenation|aorfb_active_materials",
      "title_cn": "中文全称",
      "title_en": "English short name",
      "research_domain": "研究领域",
      "main_figure_node_count": 8,
      "direct_evolution_count": 0,        // 仅 direct_evolution 全图计数
      "baseline_comparison_count": 0,
      "route_association_count": 0,
      "year_range": "起–止",
      "branch_count": 0,                  // 主图非基线节点的 node_type 去重数(轨/分支数)
      "evidence_boundary": "证据边界一句话",
      "recommended_use": "formal_case|exploratory_case|not_recommended",
      "data_path": "<case_id>/",
      "figure_svg_path": "<case_id>/main_figure.svg",
      "frontend_json_path": "<case_id>/frontend_case.json"
    }
  ]
}
```

## 每案例 `case_manifest.json`

| 键 | 类型 | 说明 |
|---|---|---|
| `case_id` | str | 案例键 |
| `title_cn` / `title_en` | str | 中文全称 / 英文短名 |
| `subtitle` | str | 副标题（一句话主题） |
| `research_domain` | str | 研究领域 |
| `audit_mode` | const | `read_only`（只读核查声明） |
| `audit_date` | date | 核查日期 |
| `model` | str | 生成模型 |
| `corpus_scope` | obj | 语料范围（总篇数、命中、真正相关篇数） |
| `source_document_count` | int | 语料内相关文献数 |
| `sources_in_corpus` | array | 语料内来源清单（S1/S2/主论文，含题录、路径、角色） |
| `statistics` | obj | 全量统计（节点、三类关系数、类型分布、主图节点/边数及线型分布） |
| `main_figure` | obj | 主图规格（样式、宽高比、8 节点/边、文件清单） |
| `evidence_boundary` | str | 证据边界声明 |
| `primary_source_status` | str | 一次论文是否独立核验 |
| `single_source_bias` | str | 单源偏置说明 |
| `constraints_honored` | array | 已遵守的诚信约束（不补造/不声称首次/关系判据等） |
| `recommended_use` | enum | `formal_case`/`exploratory_case`/`not_recommended` |
| `figure_version` | str | 采用的图形版本（如 `8节点双轨` / `8节点四分支时间轴`） |
| `notes` | array | 备注（订正、仅展示连接线、计数口径等） |

## `recommended_use` 判定口径
- `formal_case`：语料内有可支撑 8 节点主图的系统性来源、关系证据（至少含明确 direct_evolution 或经核验的方法学谱系），可作论文正式主图案例。
- `exploratory_case`：线索成立但证据密度/独立性不足，仅作探索性展示。
- `not_recommended`：证据过弱或矛盾未决，不建议作为案例。

## 校验规则
1. `all_cases_manifest.cases[*].direct_evolution_count` == 对应 edges.csv 中 `relation_class=direct_evolution` 行数。
2. `main_figure_node_count` == nodes.csv 中 `main_figure=true` 行数 == 8。
3. `branch_count` == 主图非基线节点 `node_type` 去重数。
4. 三案例 `title_cn` 与 case_summary.csv 一致。
