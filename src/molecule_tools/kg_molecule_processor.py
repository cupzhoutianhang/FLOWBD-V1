"""
知识图谱分子批量查询工具

功能：
1. 批量处理知识图谱 JSON 文件
2. 提取所有 Material/Species 类型的实体
3. 使用 LLM 将物质名称转换为 SMILES
4. 调用 DeepChem/RDKit 查询分子性质
5. 生成查询报告（成功/失败分开记录）

使用方法：
    python kg_molecule_processor.py --input_dir ./kg_jsons --output_dir ./results
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class MoleculeCandidate:
    """分子候选"""
    original_name: str              # 原始名称（来自知识图谱）
    entity_id: str                  # 实体ID
    entity_type: str                # 实体类型 (Material/Species)
    source_file: str                # 来源文件
    smiles: Optional[str] = None    # 转换得到的SMILES
    is_valid_molecule: bool = False # 是否是有效分子
    conversion_method: str = ""     # 转换方法 (library/llm/pubchem)
    conversion_confidence: float = 0.0


@dataclass
class MoleculeQueryResult:
    """分子查询结果"""
    candidate: MoleculeCandidate
    query_success: bool = False
    basic_properties: Dict[str, Any] = field(default_factory=dict)
    deepchem_data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


@dataclass 
class ProcessingReport:
    """处理报告"""
    total_files: int = 0
    processed_files: int = 0
    total_entities: int = 0
    unique_molecules: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    processing_time: float = 0.0
    timestamp: str = ""


# ============================================================================
# 分子名称转换器
# ============================================================================

class MoleculeNameConverter:
    """分子名称转换器 - 将化学物质名称转换为 SMILES"""
    
    def __init__(self, llm_config=None, use_pubchem: bool = True):
        """
        Args:
            llm_config: LLM 配置对象（需要有 call_llm 方法）
            use_pubchem: 是否使用 PubChem API
        """
        self.llm = llm_config
        self.use_pubchem = use_pubchem
        self._init_local_library()
        self._init_rdkit()
        
        # 缓存已转换的名称
        self.conversion_cache: Dict[str, Tuple[Optional[str], str]] = {}
    
    def _init_rdkit(self):
        """初始化 RDKit"""
        try:
            from rdkit import Chem
            self.Chem = Chem
            self.rdkit_available = True
        except ImportError:
            self.rdkit_available = False
            logger.warning("RDKit 未安装")
    
    def _init_local_library(self):
        """初始化本地分子库 - 常见化学物质"""
        self.local_library = {
            # 基础无机物
            "h2so4": "OS(=O)(=O)O",
            "sulfuric acid": "OS(=O)(=O)O",
            "硫酸": "OS(=O)(=O)O",
            "hcl": "Cl",
            "hydrochloric acid": "Cl",
            "盐酸": "Cl",
            "naoh": "[Na+].[OH-]",
            "sodium hydroxide": "[Na+].[OH-]",
            "氢氧化钠": "[Na+].[OH-]",
            "koh": "[K+].[OH-]",
            "potassium hydroxide": "[K+].[OH-]",
            "氢氧化钾": "[K+].[OH-]",
            "h2o": "O",
            "water": "O",
            "水": "O",
            "h2o2": "OO",
            "hydrogen peroxide": "OO",
            "过氧化氢": "OO",
            
            # 常见有机物
            "ethylene diamine": "NCCN",
            "乙二胺": "NCCN",
            "p-phenylenediamine": "Nc1ccc(N)cc1",
            "对苯二胺": "Nc1ccc(N)cc1",
            "1,4-benzoquinone": "O=C1C=CC(=O)C=C1",
            "benzoquinone": "O=C1C=CC(=O)C=C1",
            "苯醌": "O=C1C=CC(=O)C=C1",
            "1,4-苯醌": "O=C1C=CC(=O)C=C1",
            "hydroquinone": "Oc1ccc(O)cc1",
            "氢醌": "Oc1ccc(O)cc1",
            "对苯二酚": "Oc1ccc(O)cc1",
            
            # 醌类
            "anthraquinone": "O=C1c2ccccc2C(=O)c2ccccc12",
            "蒽醌": "O=C1c2ccccc2C(=O)c2ccccc12",
            "naphthoquinone": "O=C1C=CC(=O)c2ccccc12",
            "萘醌": "O=C1C=CC(=O)c2ccccc12",
            "naphthalene-1,4,5,8-tetracarboxylic acid dianhydride": "O=C1OC(=O)c2cc3C(=O)OC(=O)c3cc12",
            
            # 吩嗪类
            "phenazine": "c1ccc2nc3ccccc3nc2c1",
            "吩嗪": "c1ccc2nc3ccccc3nc2c1",
            
            # TEMPO类
            "tempo": "CC1(C)CCCC(C)(C)N1[O]",
            "4-oh-tempo": "CC1(C)CC(O)CC(C)(C)N1[O]",
            "4-hydroxy-tempo": "CC1(C)CC(O)CC(C)(C)N1[O]",
            
            # 紫精类
            "methyl viologen": "C[n+]1ccc(-c2cc[n+](C)cc2)cc1",
            "甲基紫精": "C[n+]1ccc(-c2cc[n+](C)cc2)cc1",
            
            # 溶剂
            "acetonitrile": "CC#N",
            "乙腈": "CC#N",
            "dmso": "CS(=O)C",
            "dimethyl sulfoxide": "CS(=O)C",
            "二甲基亚砜": "CS(=O)C",
            "dmf": "CN(C)C=O",
            "dimethylformamide": "CN(C)C=O",
            "二甲基甲酰胺": "CN(C)C=O",
            "propylene carbonate": "CC1COC(=O)O1",
            "碳酸丙烯酯": "CC1COC(=O)O1",
            
            # 金属配合物/离子
            "ferrocyanide": "[Fe-4](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
            "亚铁氰化物": "[Fe-4](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
            "ferricyanide": "[Fe-3](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
            "铁氰化物": "[Fe-3](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
            "ferrocene": "[Fe+2].c1cc[cH-]c1.c1cc[cH-]c1",
            "二茂铁": "[Fe+2].c1cc[cH-]c1.c1cc[cH-]c1",
            
            # 聚合物单体/常见结构
            "aniline": "Nc1ccccc1",
            "苯胺": "Nc1ccccc1",
            "pyrrole": "c1cc[nH]c1",
            "吡咯": "c1cc[nH]c1",
            "thiophene": "c1ccsc1",
            "噻吩": "c1ccsc1",
        }
        
        # 需要跳过的非分子实体
        self.skip_patterns = [
            r"^carbon\s*(paper|felt|cloth|fiber)",
            r"^nafion",
            r"membrane",
            r"electrode",
            r"separator",
            r"^graphite",
            r"battery",
            r"^rfb",
            r"^vfb",
            r"slurry",
            r"electrolyte$",
            r"solution$",
            r"^\w{1,3}\d*$",  # 如 PI1, PI2, PHQ 等缩写
            r"reduced$",
            r"oxidized$",
        ]
    
    def should_skip(self, name: str) -> bool:
        """判断是否应该跳过该名称（非分子实体）"""
        name_lower = name.lower().strip()
        
        for pattern in self.skip_patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return True
        
        return False
    
    def convert(self, name: str) -> Tuple[Optional[str], str, float]:
        """将物质名称转换为 SMILES
        
        Args:
            name: 物质名称
            
        Returns:
            (SMILES, 转换方法, 置信度)
        """
        # 检查缓存
        if name in self.conversion_cache:
            smiles, method = self.conversion_cache[name]
            return smiles, method, 0.9 if smiles else 0.0
        
        name_lower = name.lower().strip()
        
        # 1. 检查本地库
        if name_lower in self.local_library:
            smiles = self.local_library[name_lower]
            self.conversion_cache[name] = (smiles, "local_library")
            return smiles, "local_library", 1.0
        
        # 2. 尝试 PubChem API
        if self.use_pubchem:
            smiles = self._query_pubchem(name)
            if smiles:
                self.conversion_cache[name] = (smiles, "pubchem")
                return smiles, "pubchem", 0.95
        
        # 3. 使用 LLM
        if self.llm:
            smiles = self._convert_with_llm(name)
            if smiles and self._validate_smiles(smiles):
                self.conversion_cache[name] = (smiles, "llm")
                return smiles, "llm", 0.7
        
        # 转换失败
        self.conversion_cache[name] = (None, "failed")
        return None, "failed", 0.0
    
    def _query_pubchem(self, name: str) -> Optional[str]:
        """通过 PubChem API 查询 SMILES"""
        try:
            import requests
            
            # URL 编码名称
            from urllib.parse import quote
            encoded_name = quote(name)
            
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/property/CanonicalSMILES/JSON"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                smiles = data.get("PropertyTable", {}).get("Properties", [{}])[0].get("CanonicalSMILES")
                if smiles:
                    logger.debug(f"PubChem: {name} -> {smiles}")
                    return smiles
        except Exception as e:
            logger.debug(f"PubChem 查询失败 ({name}): {e}")
        
        return None
    
    def _convert_with_llm(self, name: str) -> Optional[str]:
        """使用 LLM 转换分子名称"""
        if not self.llm:
            return None
        
        prompt = f"""你是一个化学专家。请将以下化学物质名称转换为 SMILES 表示。

物质名称: {name}

要求：
1. 只返回 SMILES 字符串，不要其他任何文字
2. 如果无法确定或者这不是一个具体的分子（如聚合物、混合物、设备等），返回 "UNKNOWN"
3. 使用标准的 SMILES 格式

SMILES:"""
        
        try:
            response = self.llm.call_llm(prompt, temperature=0.1, max_tokens=100)
            
            if response and "❌" not in response:
                # 清理响应
                smiles = response.strip().split()[0].strip()
                
                if smiles and smiles.upper() != "UNKNOWN" and len(smiles) > 1:
                    # 基础验证
                    if self._validate_smiles(smiles):
                        logger.debug(f"LLM: {name} -> {smiles}")
                        return smiles
        except Exception as e:
            logger.debug(f"LLM 转换失败 ({name}): {e}")
        
        return None
    
    def _validate_smiles(self, smiles: str) -> bool:
        """验证 SMILES 有效性"""
        if not self.rdkit_available:
            return True  # 无法验证时假设有效
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            return mol is not None
        except:
            return False


# ============================================================================
# DeepChem 查询器
# ============================================================================

class DeepChemQuerier:
    """DeepChem 数据集查询器"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.expanduser("~/.deepchem_cache")
        self.loaded_datasets = {}
        self._init_deepchem()
        self._init_rdkit()
    
    def _init_deepchem(self):
        """初始化 DeepChem"""
        try:
            import deepchem as dc
            self.dc = dc
            self.deepchem_available = True
            logger.info("✓ DeepChem 可用")
        except ImportError:
            self.deepchem_available = False
            logger.warning("⚠️ DeepChem 未安装，将只计算基础性质")
    
    def _init_rdkit(self):
        """初始化 RDKit"""
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, rdMolDescriptors
            self.Chem = Chem
            self.Descriptors = Descriptors
            self.rdMolDescriptors = rdMolDescriptors
            self.rdkit_available = True
        except ImportError:
            self.rdkit_available = False
            logger.warning("⚠️ RDKit 未安装")
    
    def compute_basic_properties(self, smiles: str) -> Dict[str, Any]:
        """计算基础分子性质"""
        if not self.rdkit_available:
            return {}
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol is None:
                return {}
            
            return {
                "molecular_formula": self.rdMolDescriptors.CalcMolFormula(mol),
                "molecular_weight": round(self.Descriptors.MolWt(mol), 2),
                "logP": round(self.Descriptors.MolLogP(mol), 2),
                "TPSA": round(self.Descriptors.TPSA(mol), 2),
                "num_H_donors": self.Descriptors.NumHDonors(mol),
                "num_H_acceptors": self.Descriptors.NumHAcceptors(mol),
                "num_rotatable_bonds": self.Descriptors.NumRotatableBonds(mol),
                "num_rings": self.Descriptors.RingCount(mol),
                "formal_charge": self.Chem.GetFormalCharge(mol),
            }
        except Exception as e:
            logger.error(f"计算基础性质失败: {e}")
            return {}
    
    def search_datasets(self, smiles: str) -> Dict[str, Any]:
        """在 MoleculeNet 数据集中搜索"""
        if not self.deepchem_available:
            return {}
        
        results = {}
        
        # 要搜索的数据集
        datasets_to_search = [
            ("delaney", "ESOL水溶解度"),
            ("lipo", "亲脂性"),
            ("freesolv", "水合自由能"),
            ("bace", "BACE-1活性"),
            ("clintox", "临床毒性"),
            ("tox21", "Tox21毒性"),
        ]
        
        for dataset_name, description in datasets_to_search:
            try:
                match = self._search_single_dataset(dataset_name, smiles)
                if match:
                    results[dataset_name] = {
                        "description": description,
                        "tasks": match["tasks"],
                        "values": match["values"],
                        "split": match["split"]
                    }
            except Exception as e:
                logger.debug(f"搜索 {dataset_name} 失败: {e}")
        
        return results
    
    def _search_single_dataset(self, dataset_name: str, smiles: str) -> Optional[Dict]:
        """在单个数据集中搜索"""
        # 加载数据集
        if dataset_name not in self.loaded_datasets:
            try:
                loader = getattr(self.dc.molnet, f"load_{dataset_name}")
                tasks, datasets, transformers = loader(
                    featurizer='ECFP',
                    data_dir=self.cache_dir,
                    reload=True
                )
                self.loaded_datasets[dataset_name] = {
                    "tasks": tasks,
                    "train": datasets[0],
                    "valid": datasets[1] if len(datasets) > 1 else None,
                    "test": datasets[2] if len(datasets) > 2 else None,
                }
            except Exception as e:
                logger.debug(f"加载数据集 {dataset_name} 失败: {e}")
                return None
        
        dataset_info = self.loaded_datasets[dataset_name]
        
        # 标准化 SMILES
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol:
                canonical = self.Chem.MolToSmiles(mol, canonical=True)
            else:
                canonical = smiles
        except:
            canonical = smiles
        
        # 搜索
        for split_name in ["train", "valid", "test"]:
            dataset = dataset_info.get(split_name)
            if dataset is None:
                continue
            
            for i, mol_id in enumerate(dataset.ids):
                try:
                    ref_mol = self.Chem.MolFromSmiles(str(mol_id))
                    if ref_mol:
                        ref_canonical = self.Chem.MolToSmiles(ref_mol, canonical=True)
                        if canonical == ref_canonical:
                            return {
                                "tasks": dataset_info["tasks"],
                                "values": dataset.y[i].tolist() if hasattr(dataset.y[i], 'tolist') else list(dataset.y[i]),
                                "split": split_name
                            }
                except:
                    continue
        
        return None
    
    def query(self, smiles: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """完整查询
        
        Returns:
            (基础性质, DeepChem数据)
        """
        basic = self.compute_basic_properties(smiles)
        deepchem_data = self.search_datasets(smiles)
        
        return basic, deepchem_data


# ============================================================================
# 知识图谱处理器
# ============================================================================

class KGMoleculeProcessor:
    """知识图谱分子批量处理器"""
    
    def __init__(self,
                 llm_config=None,
                 use_pubchem: bool = True,
                 deepchem_cache_dir: str = None,
                 max_workers: int = 4):
        """
        Args:
            llm_config: LLM 配置（需要有 call_llm 方法）
            use_pubchem: 是否使用 PubChem API
            deepchem_cache_dir: DeepChem 缓存目录
            max_workers: 并行处理的线程数
        """
        logger.info("="*60)
        logger.info("初始化知识图谱分子处理器")
        logger.info("="*60)
        
        self.converter = MoleculeNameConverter(llm_config, use_pubchem)
        self.querier = DeepChemQuerier(deepchem_cache_dir)
        self.max_workers = max_workers
        
        # 处理统计
        self.processed_entities: Set[str] = set()
        self.skipped_files: List[Dict[str, str]] = []  # 记录跳过的文件
        
        logger.info("✓ 初始化完成\n")
    
    def extract_molecules_from_kg(self, kg_data: Dict) -> List[MoleculeCandidate]:
        """从知识图谱中提取分子候选"""
        candidates = []
        
        # 确保 kg_data 是字典
        if not isinstance(kg_data, dict):
            logger.warning(f"知识图谱数据格式错误，期望字典但得到 {type(kg_data).__name__}")
            return candidates
        
        # 获取实体列表——处理多种可能的数据结构
        entities = kg_data.get("data", {}).get("entities", [])
        
        # 如果不是列表，返回空列表
        if not isinstance(entities, list):
            logger.warning(f"实体不是列表，而是 {type(entities).__name__}")
            return candidates
        
        for entity in entities:
            entity_type = entity.get("type", "")
            entity_name = entity.get("name", "")
            entity_id = entity.get("id", "")
            
            # 只处理 Material 和 Species 类型
            if entity_type not in ["Material", "Species"]:
                continue
            
            # 跳过非分子实体
            if self.converter.should_skip(entity_name):
                logger.debug(f"跳过: {entity_name} (非分子实体)")
                continue
            
            # 避免重复处理
            if entity_name.lower() in self.processed_entities:
                continue
            
            candidates.append(MoleculeCandidate(
                original_name=entity_name,
                entity_id=entity_id,
                entity_type=entity_type,
                source_file=""  # 稍后填充
            ))
        
        return candidates
    
    def process_candidate(self, candidate: MoleculeCandidate) -> MoleculeQueryResult:
        """处理单个分子候选"""
        result = MoleculeQueryResult(candidate=candidate)
        
        # 步骤1: 名称转换
        smiles, method, confidence = self.converter.convert(candidate.original_name)
        
        candidate.smiles = smiles
        candidate.conversion_method = method
        candidate.conversion_confidence = confidence
        candidate.is_valid_molecule = smiles is not None
        
        if not smiles:
            result.error_message = f"无法转换为SMILES (方法: {method})"
            return result
        
        # 步骤2: 查询性质
        try:
            basic, deepchem_data = self.querier.query(smiles)
            
            result.basic_properties = basic
            result.deepchem_data = deepchem_data
            result.query_success = bool(basic) or bool(deepchem_data)
            
            if not result.query_success:
                result.error_message = "无法计算性质或在数据集中未找到"
                
        except Exception as e:
            result.error_message = f"查询失败: {str(e)}"
        
        return result
    
    def process_kg_file(self, filepath: str) -> Optional[Tuple[List[MoleculeQueryResult], List[MoleculeQueryResult]]]:
        """处理单个知识图谱文件
        
        Returns:
            (成功的结果列表, 失败的结果列表) 或 None（如果文件格式有问题）
        """
        logger.info(f"处理文件: {os.path.basename(filepath)}")
        
        # 读取 JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # 如果内容为空或不是有效的 JSON，返回空列表
                if not content.strip():
                    error_msg = "文件为空"
                    logger.error(f"  ❌ {error_msg}")
                    self.skipped_files.append({
                        "filename": os.path.basename(filepath),
                        "reason": error_msg
                    })
                    return None
                kg_data = json.loads(content)
                # 再次检查加载结果是否为字典
                if not isinstance(kg_data, dict):
                    error_msg = f"JSON 根元素不是对象，而是 {type(kg_data).__name__}"
                    logger.error(f"  ❌ {error_msg}")
                    self.skipped_files.append({
                        "filename": os.path.basename(filepath),
                        "reason": error_msg
                    })
                    return None
        except json.JSONDecodeError as e:
            error_msg = f"JSON 解析失败: {str(e)[:100]}"
            logger.error(f"  ❌ {error_msg}")
            self.skipped_files.append({
                "filename": os.path.basename(filepath),
                "reason": error_msg
            })
            return None
        except Exception as e:
            error_msg = f"读取失败: {str(e)[:100]}"
            logger.error(f"  ❌ {error_msg}")
            self.skipped_files.append({
                "filename": os.path.basename(filepath),
                "reason": error_msg
            })
            return None
        
        # 提取分子候选
        try:
            candidates = self.extract_molecules_from_kg(kg_data)
        except Exception as e:
            error_msg = f"提取分子候选失败: {str(e)[:100]}"
            logger.error(f"  \u274c {error_msg}")
            self.skipped_files.append({
                "filename": os.path.basename(filepath),
                "reason": error_msg
            })
            return None
        logger.info(f"  \u63d0\u53d6\u5230 {len(candidates)} \u4e2a\u5206\u5b50\u5019\u9009")
        
        successful = []
        failed = []
        
        for candidate in candidates:
            candidate.source_file = os.path.basename(filepath)
            
            # 记录已处理
            self.processed_entities.add(candidate.original_name.lower())
            
            # 处理
            result = self.process_candidate(candidate)
            
            if result.query_success:
                successful.append(result)
                logger.info(f"    ✓ {candidate.original_name} -> {candidate.smiles}")
            else:
                failed.append(result)
                logger.debug(f"    ✗ {candidate.original_name}: {result.error_message}")
        
        logger.info(f"  完成: {len(successful)} 成功, {len(failed)} 失败")
        return successful, failed
    
    def process_directory(self, 
                          input_dir: str, 
                          output_dir: str,
                          file_pattern: str = "*.json") -> ProcessingReport:
        """批量处理目录中的所有知识图谱文件
        
        Args:
            input_dir: 输入目录（包含 JSON 文件）
            output_dir: 输出目录
            file_pattern: 文件匹配模式
            
        Returns:
            处理报告
        """
        start_time = time.time()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 查找所有 JSON 文件
        input_path = Path(input_dir)
        json_files = list(input_path.glob(file_pattern))
        
        if not json_files:
            logger.warning(f"未找到匹配的文件: {input_dir}/{file_pattern}")
            return ProcessingReport()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"开始批量处理")
        logger.info(f"{'='*60}")
        logger.info(f"输入目录: {input_dir}")
        logger.info(f"输出目录: {output_dir}")
        logger.info(f"文件数量: {len(json_files)}")
        logger.info(f"{'='*60}\n")
        
        all_successful = []
        all_failed = []
        self.skipped_files = []  # 重置跳过的文件列表
        
        # 处理每个文件
        for i, filepath in enumerate(json_files, 1):
            logger.info(f"[{i}/{len(json_files)}] 处理文件: {os.path.basename(str(filepath))}")
            result = self.process_kg_file(str(filepath))
            # 检查是否返回错误标志（跳过的文件）
            if result is None:
                continue
            successful, failed = result
            all_successful.extend(successful)
            all_failed.extend(failed)
        
        # 生成报告
        report = ProcessingReport(
            total_files=len(json_files),
            processed_files=len(json_files),
            total_entities=len(all_successful) + len(all_failed),
            unique_molecules=len(self.processed_entities),
            successful_queries=len(all_successful),
            failed_queries=len(all_failed),
            processing_time=time.time() - start_time,
            timestamp=datetime.now().isoformat()
        )
        
        # 保存结果
        self._save_results(output_dir, all_successful, all_failed, report)
        
        # 保存跳过的文件列表
        if self.skipped_files:
            with open(os.path.join(output_dir, "skipped_files.json"), 'w', encoding='utf-8') as f:
                json.dump(self.skipped_files, f, indent=2, ensure_ascii=False)
            logger.info(f"\n⚠️ 跳过了 {len(self.skipped_files)} 个格式有问题的文件，详见 skipped_files.json")
        
        # 打印摘要
        self._print_summary(report)
        
        return report
    
    def _save_results(self,
                      output_dir: str,
                      successful: List[MoleculeQueryResult],
                      failed: List[MoleculeQueryResult],
                      report: ProcessingReport):
        """保存处理结果"""
        
        # 1. 保存成功的查询结果
        successful_data = []
        for result in successful:
            entry = {
                "original_name": result.candidate.original_name,
                "smiles": result.candidate.smiles,
                "conversion_method": result.candidate.conversion_method,
                "source_file": result.candidate.source_file,
                "entity_type": result.candidate.entity_type,
                "basic_properties": result.basic_properties,
                "deepchem_data": result.deepchem_data
            }
            successful_data.append(entry)
        
        with open(os.path.join(output_dir, "successful_queries.json"), 'w', encoding='utf-8') as f:
            json.dump(successful_data, f, indent=2, ensure_ascii=False)
        
        # 2. 保存失败的查询
        failed_data = []
        for result in failed:
            entry = {
                "original_name": result.candidate.original_name,
                "smiles": result.candidate.smiles,
                "conversion_method": result.candidate.conversion_method,
                "source_file": result.candidate.source_file,
                "entity_type": result.candidate.entity_type,
                "error": result.error_message
            }
            failed_data.append(entry)
        
        with open(os.path.join(output_dir, "failed_queries.json"), 'w', encoding='utf-8') as f:
            json.dump(failed_data, f, indent=2, ensure_ascii=False)
        
        # 3. 保存处理报告
        with open(os.path.join(output_dir, "processing_report.json"), 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        
        # 4. 保存跳过的文件列表
        if self.skipped_files:
            with open(os.path.join(output_dir, "skipped_files.json"), 'w', encoding='utf-8') as f:
                json.dump(self.skipped_files, f, indent=2, ensure_ascii=False)
            logger.info(f"⚠️ 跳过了 {len(self.skipped_files)} 个格式有问题的文件")
        
        # 5. 生成人类可读的摘要
        self._generate_readable_summary(output_dir, successful_data, failed_data, report)
        
        logger.info(f"\n结果已保存到: {output_dir}")
    
    def _generate_readable_summary(self,
                                    output_dir: str,
                                    successful: List[Dict],
                                    failed: List[Dict],
                                    report: ProcessingReport):
        """生成人类可读的摘要文件"""
        
        summary_path = os.path.join(output_dir, "SUMMARY.md")
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("# 知识图谱分子查询结果摘要\n\n")
            f.write(f"生成时间: {report.timestamp}\n\n")
            
            f.write("## 统计信息\n\n")
            f.write(f"- 处理文件数: {report.total_files}\n")
            f.write(f"- 提取实体数: {report.total_entities}\n")
            f.write(f"- 唯一分子数: {report.unique_molecules}\n")
            f.write(f"- 成功查询: {report.successful_queries}\n")
            f.write(f"- 失败查询: {report.failed_queries}\n")
            f.write(f"- 跳过文件: {len(self.skipped_files)}\n")
            f.write(f"- 处理时间: {report.processing_time:.2f} 秒\n\n")
            
            # 添加跳过文件信息
            if self.skipped_files:
                f.write("## 跳过的文件（格式有问题）\n\n")
                f.write("| 文件名 | 原因 |\n")
                f.write("|---------|------|\n")
                for skip_info in self.skipped_files:
                    filename = skip_info["filename"]
                    reason = skip_info["reason"]
                    f.write(f"| {filename} | {reason} |\n")
                f.write("\n")
            
            f.write("## 成功查询的分子\n\n")
            if successful:
                f.write("| 名称 | SMILES | 分子式 | 分子量 | LogP | DeepChem数据 |\n")
                f.write("|------|--------|--------|--------|------|-------------|\n")
                for mol in successful[:50]:  # 只显示前50个
                    name = mol["original_name"]
                    smiles = mol["smiles"][:30] + "..." if len(mol["smiles"]) > 30 else mol["smiles"]
                    formula = mol["basic_properties"].get("molecular_formula", "N/A")
                    mw = mol["basic_properties"].get("molecular_weight", "N/A")
                    logp = mol["basic_properties"].get("logP", "N/A")
                    dc_data = "有" if mol["deepchem_data"] else "无"
                    f.write(f"| {name} | {smiles} | {formula} | {mw} | {logp} | {dc_data} |\n")
                
                if len(successful) > 50:
                    f.write(f"\n*（仅显示前50个，共{len(successful)}个）*\n")
            else:
                f.write("无\n")
            
            f.write("\n## 未能查询的实体\n\n")
            if failed:
                f.write("| 名称 | 来源文件 | 原因 |\n")
                f.write("|------|----------|------|\n")
                for mol in failed[:30]:
                    name = mol["original_name"]
                    source = mol["source_file"]
                    error = mol["error"][:50] if mol["error"] else "未知"
                    f.write(f"| {name} | {source} | {error} |\n")
                
                if len(failed) > 30:
                    f.write(f"\n*（仅显示前30个，共{len(failed)}个）*\n")
            else:
                f.write("无\n")
    
    def _print_summary(self, report: ProcessingReport):
        """打印处理摘要"""
        logger.info(f"\n{'='*60}")
        logger.info("处理完成")
        logger.info(f"{'='*60}")
        logger.info(f"  处理文件: {report.total_files}")
        logger.info(f"  提取实体: {report.total_entities}")
        logger.info(f"  唯一分子: {report.unique_molecules}")
        logger.info(f"  成功查询: {report.successful_queries}")
        logger.info(f"  失败查询: {report.failed_queries}")
        logger.info(f"  处理时间: {report.processing_time:.2f} 秒")
        logger.info(f"{'='*60}")


# ============================================================================
# LLM 配置适配器
# ============================================================================

class SimpleLLMConfig:
    """简单的 LLM 配置，兼容 Kimi API"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or __import__("os").environ.get("MOONSHOT_API_KEY", "")
        self.base_url = base_url or "https://api.moonshot.cn/v1"
        self.model = "moonshot-v1-8k"
    
    def call_llm(self, prompt: str, temperature: float = 0.3, max_tokens: int = 500) -> str:
        """调用 LLM"""
        import requests
        
        if not self.api_key:
            return ""
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=(10, 60)
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.debug(f"LLM 调用失败: {e}")
        
        return ""


# ============================================================================
# 命令行接口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="知识图谱分子批量查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单个目录
  python kg_molecule_processor.py --input_dir ./kg_jsons --output_dir ./results

  # 指定 API Key
  python kg_molecule_processor.py --input_dir ./kg_jsons --output_dir ./results --api_key YOUR_KEY

  # 不使用 PubChem（更快但覆盖率更低）
  python kg_molecule_processor.py --input_dir ./kg_jsons --output_dir ./results --no-pubchem

  # 处理单个文件
  python kg_molecule_processor.py --input_file ./test.json --output_dir ./results
        """
    )
    
    parser.add_argument("--input_dir", type=str, help="输入目录（包含 JSON 文件）")
    parser.add_argument("--input_file", type=str, help="单个输入文件")
    parser.add_argument("--output_dir", type=str, default="./molecule_query_results", help="输出目录")
    parser.add_argument("--api_key", type=str, help="Kimi API Key（用于 LLM 转换）")
    parser.add_argument("--no-pubchem", action="store_true", help="不使用 PubChem API")
    parser.add_argument("--no-llm", action="store_true", help="不使用 LLM 转换")
    parser.add_argument("--pattern", type=str, default="*.json", help="文件匹配模式")
    parser.add_argument("--workers", type=int, default=4, help="并行线程数")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 初始化 LLM
    llm_config = None
    if not args.no_llm:
        api_key = args.api_key or os.environ.get("KIMI_API_KEY", __import__("os").environ.get("MOONSHOT_API_KEY", ""))
        if api_key:
            llm_config = SimpleLLMConfig(api_key=api_key)
            logger.info("✓ LLM 已配置")
        else:
            logger.warning("⚠️ 未提供 API Key，LLM 转换功能不可用")
    
    # 初始化处理器
    processor = KGMoleculeProcessor(
        llm_config=llm_config,
        use_pubchem=not args.no_pubchem,
        max_workers=args.workers
    )
    
    # 处理
    if args.input_file:
        # 单个文件
        result = processor.process_kg_file(args.input_file)
        
        # 检查是否为有效的结果
        if result is None:
            logger.error("文件格式有错误，无法处理")
            sys.exit(1)
        
        successful, failed = result
        
        # 保存结果
        os.makedirs(args.output_dir, exist_ok=True)
        processor._save_results(
            args.output_dir,
            successful,
            failed,
            ProcessingReport(
                total_files=1,
                processed_files=1,
                total_entities=len(successful) + len(failed),
                successful_queries=len(successful),
                failed_queries=len(failed),
                timestamp=datetime.now().isoformat()
            )
        )
        
    elif args.input_dir:
        # 目录
        processor.process_directory(
            args.input_dir,
            args.output_dir,
            args.pattern
        )
    else:
        parser.print_help()
        print("\n错误: 请指定 --input_dir 或 --input_file")
        sys.exit(1)


if __name__ == "__main__":
    main()
