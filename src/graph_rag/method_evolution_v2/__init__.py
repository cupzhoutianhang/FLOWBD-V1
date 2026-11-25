"""method_evolution_v2: 与 legacy method_extraction / rag 完全解耦的 V2 模块.

V2 权威输入仅包括:
  1. pdf_to_md/extraction_results/downloaded_files/<paper>/full.md
  2. 原始 PDF (仅溯源, 不修改)
  3. publish_year_report.csv (仅作年份参考)

V2 禁止读取以下作为输入 (仅 legacy 对照):
  - src/graph_rag/method_extraction/methods.csv
  - src/graph_rag/method_extraction/edges.csv
  - src/graph_rag/method_extraction/method_outputs/*.json
  - paper/data/methods_v2.csv
  - paper/data/methods_v3.csv
  - paper/data/edges_v2.csv
"""
