# 统一视觉风格规范（visual_style_guide.md）

> 三张主图（PCM / CO·CO₂ / AORFB）**必须共用本规范**：同字体、同字号、同线宽、同圆角、
> 同箭头、同图例。差异仅允许出现在"节点数/分支数/年份轴刻度"这类**由数据决定**的地方。

## 1. 画布与排版
| 项 | 值 |
|---|---|
| 方向 | `rankdir=LR`（左→右 = 旧→新） |
| 背景 | 纯白 `white` |
| 目标宽高比 | **2.8 : 1 ～ 3.2 : 1**（实测 PCM 2.82 / CO 3.02 / AORFB 3.19） |
| 建议正文宽 | 单栏 16 cm（`main_figure_16cm.png`，1890 px）；整版用矢量 `main_figure.pdf` |
| pad / margin | `pad=0.10` / `margin=0` |
| 布局微调 | `splines=spline`、`newrank=true`、`ratio=compress`；`ranksep`/`nodesep` 按案例调至目标宽高比 |

## 2. 节点样式（全图一致）
| 项 | 值 |
|---|---|
| 形状 | `box, style="rounded,filled"`（圆角矩形） |
| 字体 | `Microsoft YaHei` |
| 节点字号 | `11` |
| 内边距 | `margin="0.14,0.09"` |
| 边框线宽 | `penwidth=1.4` |
| 文字色 | `#111827` |

### 节点配色（node_type → 填充/边框）
| node_type | 含义 | 填充 fill | 边框 border |
|---|---|---|---|
| `baseline` | 基线（传统/无机对照） | `#E5E7EB` 浅灰 | `#6B7280` 深灰 |
| `track_primary` | 主路线 1 | `#DBEAFE` 浅蓝 | `#2563EB` 蓝 |
| `track_secondary` | 主路线 2 | `#DCFCE7` 浅绿 | `#16A34A` 绿 |
| `track_tertiary` | 第 3 分支（PCM 观察法等） | `#FFEDD5` 浅橙 | `#DD6B20` 橙 |
| `track_quaternary` | 第 4 分支（PCM 综合判定法等） | `#EDE9FE` 浅紫 | `#7C3AED` 紫 |
| `auxiliary_c..f` | 非主图辅助节点（仅数据层） | 见下 | — |

> 辅助色（仅用于全量数据/非 8 节点主图，主图不出现）：
> `auxiliary_c=#FFEDD5`、`auxiliary_d=#EDE9FE`、`auxiliary_e=#CCFBF1`、`auxiliary_f=#FCE7F3`。
> **8 节点主图只用 baseline + track_primary/secondary(+PCM 的 tertiary/quaternary)。**

## 3. 边样式（relation_class → 线型/线色/线宽，三图一致）
| relation_class | line_style | 线色 | 线宽 |
|---|---|---|---|
| `direct_evolution` | 实线 solid | `#111827` | `1.8` |
| `baseline_comparison`（相对传统基线） | 点划线 dash_dot | `#C65A00` | `1.5` |
| `node_performance_comparison`（节点级性能倍数比较，无承接） | 点划线 dash_dot | `#C65A00` | `1.5` |
| `route_association` | 虚线 dashed | `#71839B` | `1.3` |

- 箭头 `arrowsize=0.8`；边标签字号 `9`。
- **点划线实现**：dot 无原生点划线 → 先渲染 `dashed` 且加 `class="rel-basecmp"`，
  再由 `render_main_figure.py` 后处理将该组 `stroke-dasharray` 改写为 `8,3,1.5,3`。
  `baseline_comparison` 与 `node_performance_comparison` 同用 `class="rel-basecmp"`（同为橙色点划线）。
- **展示型连接（figure_only）**：仅为主图视觉连通而增设、`count_in_dataset=false` 的边，线型仍按其 relation_class（如 route_association 用虚线），但**不计入全量数据统计**（详见 `edge_schema.md`）。
- 年份轴：`plaintext` 节点用 10 号灰字，轴线 `#9CA3AF`、`penwidth=1.0`、`arrowhead=none`、`weight=100`（高权重保持水平）。

## 4. 图例（底部，顺序固定）
`labelloc=b` 的 HTML-like 表格，一行，从左到右顺序：
1. **节点色块**（baseline → track_primary → track_secondary →〔PCM 追加 tertiary/quaternary〕）
2. **实线 = 直接演化**
3. **点划线 = 基线/性能比较**（PCM 无此类，图例省略该项）
4. **虚线 = 路线归类**（PCM 无此类，图例省略该项）

图例字号 10；与正文风格一致。

## 5. 化学式排版
- `display_name`（CSV）保留 **Unicode 下标**（`Br₂`、`K₄Fe(CN)₆`、`Fe₂O₃@SiO₂`）供论文/前端排版。
- **图内标签**：因 Microsoft YaHei 缺 Unicode 下标字形（渲染为豆腐块），主图统一采用
  **基线数字**（`Br2`、`K4Fe(CN)6`、`Fe2O3@SiO2`）——可读、可检索、无歧义；
  Graphviz `<SUB>` 在当前构建下不下沉字号，故不依赖它做下标。
- 纯文本可检索名存于 `node_name` 字段。

## 6. 三图一致性硬指标（validate 检查）
| 指标 | 统一值 |
|---|---|
| 字体 | Microsoft YaHei |
| 节点字号 / 边字号 / 年份轴字号 | 11 / 9 / 10 |
| 节点边框线宽 | 1.4 |
| 实线/点划线/虚线线宽 | 1.8 / 1.5 / 1.3 |
| 圆角 | `style="rounded,filled"` |
| 箭头大小 | 0.8 |
| 直接演化线色 | `#111827` |
| 基线/性能线色 | `#C65A00` |
| 路线线色 | `#71839B` |
| 图例位置/顺序 | 底部；节点色→实线→点划线→虚线 |
