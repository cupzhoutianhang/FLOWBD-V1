"""V2 模块的路径常量与 legacy 隔离声明.

任何 V2 脚本必须只从 V2_AUTHORITATIVE_INPUTS 读取数据, 不得读取 LEGACY_PATHS_DO_NOT_INPUT.
"""
from __future__ import annotations
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
SRC_DIR = os.path.dirname(SRC_GRAPH_RAG_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# ========== V2 唯一允许的输入 ==========
DOWNLOADED_FILES_DIR = os.path.join(
    PROJECT_ROOT, "pdf_to_md", "extraction_results", "downloaded_files"
)
LEGACY_YEAR_REPORT_CSV = os.path.join(
    PROJECT_ROOT, "src", "graph_rag", "method_extraction", "publish_year_report.csv"
)

V2_AUTHORITATIVE_INPUTS = {
    "downloaded_files_dir": DOWNLOADED_FILES_DIR,
    "publish_year_report_csv_for_reference_only": LEGACY_YEAR_REPORT_CSV,
}

# ========== V2 禁止读取的 legacy 产物 (仅用于事后 diff) ==========
LEGACY_PATHS_DO_NOT_INPUT = {
    "methods_csv": os.path.join(
        PROJECT_ROOT, "src", "graph_rag", "method_extraction", "methods.csv"),
    "edges_csv": os.path.join(
        PROJECT_ROOT, "src", "graph_rag", "method_extraction", "edges.csv"),
    "method_outputs_dir": os.path.join(
        PROJECT_ROOT, "src", "graph_rag", "method_extraction", "method_outputs"),
    "paper_data_methods_v2": os.path.join(
        PROJECT_ROOT, "paper", "data", "methods_v2.csv"),
    "paper_data_methods_v3": os.path.join(
        PROJECT_ROOT, "paper", "data", "methods_v3.csv"),
    "paper_data_edges_v2": os.path.join(
        PROJECT_ROOT, "paper", "data", "edges_v2.csv"),
}

# ========== V2 产物目录 ==========
PAPER_V2_DIR = os.path.join(PROJECT_ROOT, "paper", "method_evolution_v2")
TEST_RUN_01_DIR = os.path.join(PAPER_V2_DIR, "test_run_01")
TEST_RUN_01_SECTIONS_DIR = os.path.join(TEST_RUN_01_DIR, "sections")
TEST_RUN_01_REPORT_CSV = os.path.join(TEST_RUN_01_DIR, "section_parse_report.csv")
TEST_RUN_01_REPORT_MD = os.path.join(TEST_RUN_01_DIR, "section_parse_report.md")
TEST_RUN_01_PAPER_TYPE_CSV = os.path.join(TEST_RUN_01_DIR, "paper_type_test.csv")
TEST_RUN_01_PAPER_TYPE_MD = os.path.join(TEST_RUN_01_DIR, "paper_type_test.md")
TEST_RUN_01_TAXONOMY_CSV = os.path.join(TEST_RUN_01_DIR, "taxonomy_test.csv")
TEST_RUN_01_TAXONOMY_MD = os.path.join(TEST_RUN_01_DIR, "taxonomy_test.md")

# ========== 全语料预处理 v1 (337 篇, 纯本地) ==========
CORPUS_PP_V1_DIR = os.path.join(PAPER_V2_DIR, "corpus_preprocess_v1")
CORPUS_PP_V1_SECTIONS_DIR = os.path.join(CORPUS_PP_V1_DIR, "sections")
CORPUS_PP_V1_MANIFEST_JSON = os.path.join(CORPUS_PP_V1_DIR, "source_manifest.json")
CORPUS_PP_V1_PAPER_TYPES_CSV = os.path.join(CORPUS_PP_V1_DIR, "paper_types.csv")
CORPUS_PP_V1_PAPER_TAXONOMY_CSV = os.path.join(CORPUS_PP_V1_DIR, "paper_taxonomy.csv")
CORPUS_PP_V1_REPORT_JSON = os.path.join(CORPUS_PP_V1_DIR, "preprocessing_report.json")
CORPUS_PP_V1_REPORT_MD = os.path.join(CORPUS_PP_V1_DIR, "preprocessing_report.md")
CORPUS_PP_V1_FAILED_CSV = os.path.join(CORPUS_PP_V1_DIR, "failed_papers.csv")
CORPUS_PP_V1_CANDIDATES_CSV = os.path.join(CORPUS_PP_V1_DIR, "taxonomy_candidates.csv")
CORPUS_PP_V1_UNKNOWN_CSV = os.path.join(CORPUS_PP_V1_DIR, "taxonomy_unknown.csv")
CORPUS_PP_V1_NON_STORAGE_CSV = os.path.join(CORPUS_PP_V1_DIR, "non_storage_papers.csv")
CORPUS_PP_V1_CONFLICTS_CSV = os.path.join(CORPUS_PP_V1_DIR, "taxonomy_conflicts.csv")

# ========== 全语料预处理 v1.1 (窄口径关键词补丁 + 标题分离 + 无 lab_material 默认) ==========
CORPUS_PP_V1_1_DIR = os.path.join(PAPER_V2_DIR, "corpus_preprocess_v1_1")
CORPUS_PP_V1_1_SECTIONS_DIR = os.path.join(CORPUS_PP_V1_1_DIR, "sections")
CORPUS_PP_V1_1_MANIFEST_JSON = os.path.join(CORPUS_PP_V1_1_DIR, "source_manifest.json")
CORPUS_PP_V1_1_PAPER_TYPES_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "paper_types.csv")
CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "paper_taxonomy.csv")
CORPUS_PP_V1_1_REPORT_JSON = os.path.join(CORPUS_PP_V1_1_DIR, "preprocessing_report.json")
CORPUS_PP_V1_1_REPORT_MD = os.path.join(CORPUS_PP_V1_1_DIR, "preprocessing_report.md")
CORPUS_PP_V1_1_FAILED_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "failed_papers.csv")
CORPUS_PP_V1_1_CANDIDATES_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "taxonomy_candidates.csv")
CORPUS_PP_V1_1_UNKNOWN_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "taxonomy_unknown.csv")
CORPUS_PP_V1_1_NON_STORAGE_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "non_storage_papers.csv")
CORPUS_PP_V1_1_CONFLICTS_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "taxonomy_conflicts.csv")
CORPUS_PP_V1_1_TITLES_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
CORPUS_PP_V1_1_DIFF_CSV = os.path.join(CORPUS_PP_V1_1_DIR, "preprocessing_diff_v1_to_v1_1.csv")
CORPUS_PP_V1_1_DIFF_MD = os.path.join(CORPUS_PP_V1_1_DIR, "preprocessing_diff_v1_to_v1_1.md")

# ========== Stage A (10-paper test) ==========
STAGE_A_TEST_02_DIR = os.path.join(PAPER_V2_DIR, "test_run_02_stage_a")
STAGE_A_TEST_02_LOGS_DIR = os.path.join(STAGE_A_TEST_02_DIR, "logs")
STAGE_A_TEST_02_METHODS_RAW = os.path.join(STAGE_A_TEST_02_DIR, "methods_raw.jsonl")
STAGE_A_TEST_02_METHODS_ACCEPTED = os.path.join(STAGE_A_TEST_02_DIR, "methods_accepted.csv")
STAGE_A_TEST_02_METHODS_CANDIDATE = os.path.join(STAGE_A_TEST_02_DIR, "methods_candidate.csv")
STAGE_A_TEST_02_METHODS_REJECTED = os.path.join(STAGE_A_TEST_02_DIR, "methods_rejected.csv")
STAGE_A_TEST_02_MANIFEST_JSON = os.path.join(STAGE_A_TEST_02_DIR, "extraction_manifest.json")
STAGE_A_TEST_02_VALIDATION_JSON = os.path.join(STAGE_A_TEST_02_DIR, "evidence_validation_report.json")
STAGE_A_TEST_02_VALIDATION_MD = os.path.join(STAGE_A_TEST_02_DIR, "evidence_validation_report.md")
STAGE_A_TEST_02_PER_PAPER_CSV = os.path.join(STAGE_A_TEST_02_DIR, "per_paper_summary.csv")

# ========== Stage A v2 (sentence-id 引用协议; 10-paper test) ==========
STAGE_A_TEST_03_DIR = os.path.join(PAPER_V2_DIR, "test_run_03_stage_a_sentence_ids")
STAGE_A_TEST_03_LOGS_DIR = os.path.join(STAGE_A_TEST_03_DIR, "logs")
STAGE_A_TEST_03_SENTENCE_IDX_DIR = os.path.join(STAGE_A_TEST_03_DIR, "sentence_index")
STAGE_A_TEST_03_METHODS_RAW = os.path.join(STAGE_A_TEST_03_DIR, "methods_raw.jsonl")
STAGE_A_TEST_03_METHODS_ACCEPTED = os.path.join(STAGE_A_TEST_03_DIR, "methods_accepted.csv")
STAGE_A_TEST_03_METHODS_CANDIDATE = os.path.join(STAGE_A_TEST_03_DIR, "methods_candidate.csv")
STAGE_A_TEST_03_METHODS_REJECTED = os.path.join(STAGE_A_TEST_03_DIR, "methods_rejected.csv")
STAGE_A_TEST_03_MANIFEST_JSON = os.path.join(STAGE_A_TEST_03_DIR, "extraction_manifest.json")
STAGE_A_TEST_03_VALIDATION_JSON = os.path.join(STAGE_A_TEST_03_DIR, "evidence_validation_report.json")
STAGE_A_TEST_03_VALIDATION_MD = os.path.join(STAGE_A_TEST_03_DIR, "evidence_validation_report.md")
STAGE_A_TEST_03_PER_PAPER_CSV = os.path.join(STAGE_A_TEST_03_DIR, "per_paper_summary.csv")
STAGE_A_TEST_03_DIFF_CSV = os.path.join(STAGE_A_TEST_03_DIR, "diff_v02_vs_v03.csv")
STAGE_A_TEST_03_DIFF_MD = os.path.join(STAGE_A_TEST_03_DIR, "diff_v02_vs_v03.md")

# ========== Stage B (演化关系抽取; 10-paper test) ==========
STAGE_B_TEST_04_DIR = os.path.join(PAPER_V2_DIR, "test_run_04_stage_b")
STAGE_B_TEST_04_LOGS_DIR = os.path.join(STAGE_B_TEST_04_DIR, "logs")
STAGE_B_TEST_04_CANDIDATE_PAIRS_CSV = os.path.join(STAGE_B_TEST_04_DIR, "candidate_pairs.csv")
STAGE_B_TEST_04_RELATION_RAW = os.path.join(STAGE_B_TEST_04_DIR, "relation_raw.jsonl")
STAGE_B_TEST_04_EDGES_ACCEPTED = os.path.join(STAGE_B_TEST_04_DIR, "edges_accepted.csv")
STAGE_B_TEST_04_EDGES_CANDIDATE = os.path.join(STAGE_B_TEST_04_DIR, "edges_candidate.csv")
STAGE_B_TEST_04_EDGES_REJECTED = os.path.join(STAGE_B_TEST_04_DIR, "edges_rejected.csv")
STAGE_B_TEST_04_AUDIT_JSONL = os.path.join(STAGE_B_TEST_04_DIR, "relation_audit.jsonl")
STAGE_B_TEST_04_PER_PAPER_CSV = os.path.join(STAGE_B_TEST_04_DIR, "per_paper_relation_summary.csv")
STAGE_B_TEST_04_VALIDATION_JSON = os.path.join(STAGE_B_TEST_04_DIR, "relation_validation_report.json")
STAGE_B_TEST_04_VALIDATION_MD = os.path.join(STAGE_B_TEST_04_DIR, "relation_validation_report.md")

# ========== Stage B v2 strict (10-paper test) ==========
STAGE_B_TEST_05_DIR = os.path.join(PAPER_V2_DIR, "test_run_05_stage_b_strict")
STAGE_B_TEST_05_LOGS_DIR = os.path.join(STAGE_B_TEST_05_DIR, "logs")
STAGE_B_TEST_05_CANDIDATE_PAIRS_CSV = os.path.join(STAGE_B_TEST_05_DIR, "candidate_pairs.csv")
STAGE_B_TEST_05_RELATION_RAW = os.path.join(STAGE_B_TEST_05_DIR, "relation_raw.jsonl")
STAGE_B_TEST_05_EDGES_ACCEPTED = os.path.join(STAGE_B_TEST_05_DIR, "edges_accepted.csv")
STAGE_B_TEST_05_EDGES_CANDIDATE = os.path.join(STAGE_B_TEST_05_DIR, "edges_candidate.csv")
STAGE_B_TEST_05_EDGES_REJECTED = os.path.join(STAGE_B_TEST_05_DIR, "edges_rejected.csv")
STAGE_B_TEST_05_AUDIT_JSONL = os.path.join(STAGE_B_TEST_05_DIR, "relation_audit.jsonl")
STAGE_B_TEST_05_PER_PAPER_CSV = os.path.join(STAGE_B_TEST_05_DIR, "per_paper_relation_summary.csv")
STAGE_B_TEST_05_VALIDATION_JSON = os.path.join(STAGE_B_TEST_05_DIR, "relation_validation_report.json")
STAGE_B_TEST_05_VALIDATION_MD = os.path.join(STAGE_B_TEST_05_DIR, "relation_validation_report.md")
STAGE_B_TEST_05_DIFF_CSV = os.path.join(STAGE_B_TEST_05_DIR, "diff_v04_vs_v05.csv")
STAGE_B_TEST_05_DIFF_MD = os.path.join(STAGE_B_TEST_05_DIR, "diff_v04_vs_v05.md")

# ========== Stage A full-corpus v1 (337 篇 resumable, spec 五) ==========
STAGE_A_FULL_V1_DIR = os.path.join(PAPER_V2_DIR, "stage_a_full_v1")
STAGE_A_FULL_V1_PER_PAPER_DIR = os.path.join(STAGE_A_FULL_V1_DIR, "per_paper")
STAGE_A_FULL_V1_CHECKPOINTS_DIR = os.path.join(STAGE_A_FULL_V1_DIR, "checkpoints")
STAGE_A_FULL_V1_MANIFEST_JSON = os.path.join(STAGE_A_FULL_V1_DIR, "manifest.json")
STAGE_A_FULL_V1_RUN_CONFIG_JSON = os.path.join(STAGE_A_FULL_V1_DIR, "run_config.json")
STAGE_A_FULL_V1_BUDGET_JSON = os.path.join(STAGE_A_FULL_V1_DIR, "budget_estimate.json")
STAGE_A_FULL_V1_PREFLIGHT_JSON = os.path.join(STAGE_A_FULL_V1_DIR, "preflight_report.json")
STAGE_A_FULL_V1_PREFLIGHT_MD = os.path.join(STAGE_A_FULL_V1_DIR, "preflight_report.md")
STAGE_A_FULL_V1_BATCHES_CSV = os.path.join(STAGE_A_FULL_V1_DIR, "batches.csv")
STAGE_A_FULL_V1_PAPER_ID_MAP_CSV = os.path.join(STAGE_A_FULL_V1_DIR, "paper_id_to_dir.csv")
STAGE_A_FULL_V1_FAILED_CSV = os.path.join(STAGE_A_FULL_V1_DIR, "failed_papers.csv")
STAGE_A_FULL_V1_SKIPPED_CSV = os.path.join(STAGE_A_FULL_V1_DIR, "skipped_papers.csv")
STAGE_A_FULL_V1_COST_LEDGER_CSV = os.path.join(STAGE_A_FULL_V1_DIR, "cost_ledger.csv")

# ========== Stage A local revalidation v1.1 (无 API) ==========
STAGE_A_REVALID_V1_1_DIR = os.path.join(PAPER_V2_DIR, "stage_a_validation_v1_1")
STAGE_A_REVALID_V1_1_ACCEPTED_CSV = os.path.join(STAGE_A_REVALID_V1_1_DIR, "methods_accepted_revalidated.csv")
STAGE_A_REVALID_V1_1_CANDIDATE_CSV = os.path.join(STAGE_A_REVALID_V1_1_DIR, "methods_candidate_revalidated.csv")
STAGE_A_REVALID_V1_1_REJECTED_CSV = os.path.join(STAGE_A_REVALID_V1_1_DIR, "methods_rejected_revalidated.csv")
STAGE_A_REVALID_V1_1_STATUS_CHANGES_CSV = os.path.join(STAGE_A_REVALID_V1_1_DIR, "status_changes.csv")
STAGE_A_REVALID_V1_1_VALIDATION_DIFF_MD = os.path.join(STAGE_A_REVALID_V1_1_DIR, "validation_diff.md")
STAGE_A_REVALID_V1_1_PER_PAPER_CSV = os.path.join(STAGE_A_REVALID_V1_1_DIR, "per_paper_summary.csv")

SOURCE_VERSION_LOCK_JSON = os.path.join(THIS_DIR, "source_version_lock.json")

# ========== Stage A recovery test v1 (无 own accepted 的 research 补救) ==========
STAGE_A_RECOVERY_TEST_V1_DIR = os.path.join(PAPER_V2_DIR, "stage_a_recovery_test_v1")
STAGE_A_RECOVERY_TEST_V1_PER_PAPER_DIR = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "per_paper")
STAGE_A_RECOVERY_TEST_V1_CANDIDATES_CSV = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "candidates.csv")
STAGE_A_RECOVERY_TEST_V1_COST_LEDGER_CSV = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "cost_ledger.csv")
STAGE_A_RECOVERY_TEST_V1_FAILED_CSV = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "failed_papers.csv")
STAGE_A_RECOVERY_TEST_V1_REPORT_MD = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "recovery_report.md")
STAGE_A_RECOVERY_TEST_V1_MANIFEST_JSON = os.path.join(STAGE_A_RECOVERY_TEST_V1_DIR, "manifest.json")

# ========== 试运行 10 篇 paper_id ==========
# 设计方案中第 9 篇 (氢储能 research) 选定为 基于液氖液氮梯级蓄冷的液氢储能中冷能回收利用研究
TEST_RUN_01_PAPER_IDS = [
    "全钒液流电池电堆的均一性",                                  # 电化学 / research / 液流
    "钠离子电池正极材料研究进展",                                # 电化学 / review / 钠
    "Cu阳离子空位提升钙钛矿型高熵氧化物储锂性能",                # 电化学 / research / 锂
    "三水醋酸钠相变储能复合材料改性制备及储_放热特性",           # 热 / research / 相变
    "光热-跨临界压缩二氧化碳储能循环动态特性研究",               # 机械 / research / CO2 储能
    "基于液氖液氮梯级蓄冷的液氢储能中冷能回收利用研究",          # 化学燃料 / research / 氢储能 (替换占位)
    "MOFs基材料在超级电容器中的应用",                            # review + 跨电化学
    "低共熔溶剂在储能与传热方面的研究进展",                      # review 多标签易误判
    "SMES超导磁体动态载荷温度场仿真分析",                        # magnetic / OCR 乱码典型
    "二氧化硅基气凝胶材料及其制备技术的专利分析",                # 易判 non_storage
]


def relative_path(abs_path: str) -> str:
    """转项目相对路径, 用于版本锁里的可移植记录."""
    abs_path = os.path.abspath(abs_path)
    root = os.path.abspath(PROJECT_ROOT)
    if abs_path.startswith(root):
        return os.path.relpath(abs_path, root).replace("\\", "/")
    return abs_path.replace("\\", "/")


def full_md_path(paper_id: str) -> str:
    return os.path.join(DOWNLOADED_FILES_DIR, paper_id, "full.md")
