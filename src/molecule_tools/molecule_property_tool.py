"""
分子性质查询工具 (Molecule Property Tool)
用于液流电池领域 Agentic RAG 系统的扩展模块

功能：
1. 基于 SMILES/分子名称查询分子基础性质 (RDKit)
2. 使用 DeepChem MoleculeNet 数据集检索已有实验数据
3. 使用 DeepChem 预训练模型预测分子性质
4. 液流电池领域专用分子库（常见电解质、添加剂等）

集成方式：
- 作为独立 Tool 供 Agent 调用
- 与现有 KnowledgeArsenal 无缝集成
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


# ============================================================================
# 数据结构定义
# ============================================================================

class PropertyCategory(Enum):
    """分子性质类别"""
    BASIC = "basic"                    # 基础物化性质
    SOLUBILITY = "solubility"          # 溶解度相关
    ELECTROCHEMICAL = "electrochemical" # 电化学性质
    TOXICITY = "toxicity"              # 毒性
    THERMODYNAMIC = "thermodynamic"    # 热力学性质
    STABILITY = "stability"            # 稳定性


@dataclass
class MoleculeInfo:
    """分子信息"""
    identifier: str                    # 输入标识符（名称或SMILES）
    smiles: Optional[str] = None       # 标准SMILES
    canonical_smiles: Optional[str] = None  # 规范化SMILES
    inchi: Optional[str] = None        # InChI
    inchi_key: Optional[str] = None    # InChI Key
    molecular_formula: Optional[str] = None  # 分子式
    common_names: List[str] = field(default_factory=list)  # 常用名
    is_valid: bool = False
    error: Optional[str] = None


@dataclass
class PropertyResult:
    """性质查询结果"""
    category: PropertyCategory
    property_name: str
    value: Any
    unit: Optional[str] = None
    source: str = "computed"           # computed/predicted/experimental
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MoleculeQueryResult:
    """完整的分子查询结果"""
    molecule: MoleculeInfo
    properties: List[PropertyResult] = field(default_factory=list)
    dataset_matches: List[Dict[str, Any]] = field(default_factory=list)
    rfb_relevance: Dict[str, Any] = field(default_factory=dict)  # 液流电池相关性
    query_success: bool = False
    errors: List[str] = field(default_factory=list)


# ============================================================================
# 液流电池领域分子库
# ============================================================================

class RFBMoleculeLibrary:
    """液流电池领域常见分子库
    
    收录了各类液流电池中常见的：
    - 活性物质（正极/负极）
    - 支持电解质
    - 溶剂
    - 添加剂
    """
    
    def __init__(self):
        self._init_molecule_database()
    
    def _init_molecule_database(self):
        """初始化分子数据库"""
        
        # 有机活性物质 - 负极材料 (Anolyte)
        self.anolyte_molecules = {
            # 醌类
            "anthraquinone": {
                "smiles": "O=C1c2ccccc2C(=O)c2ccccc12",
                "names": ["蒽醌", "anthraquinone", "AQ", "9,10-蒽醌"],
                "category": "quinone",
                "redox_potential": -0.09,  # vs SHE
                "electrons": 2
            },
            "AQDS": {
                "smiles": "O=C1c2cc(S(=O)(=O)O)cc(S(=O)(=O)O)c2C(=O)c2ccccc12",
                "names": ["AQDS", "蒽醌二磺酸", "9,10-anthraquinone-2,7-disulfonic acid"],
                "category": "quinone",
                "redox_potential": -0.21,
                "electrons": 2
            },
            "DHAQ": {
                "smiles": "O=C1c2cc(O)c(O)cc2C(=O)c2ccccc12",
                "names": ["DHAQ", "2,3-二羟基蒽醌", "2,3-dihydroxyanthraquinone"],
                "category": "quinone",
                "redox_potential": -0.68,
                "electrons": 2
            },
            "BQ": {
                "smiles": "O=C1C=CC(=O)C=C1",
                "names": ["苯醌", "benzoquinone", "BQ", "1,4-苯醌"],
                "category": "quinone",
                "redox_potential": 0.10,
                "electrons": 2
            },
            
            # 吩嗪类 (Phenazine)
            "phenazine": {
                "smiles": "c1ccc2nc3ccccc3nc2c1",
                "names": ["吩嗪", "phenazine", "PZ"],
                "category": "phenazine",
                "redox_potential": -0.36,
                "electrons": 2
            },
            "DHPS": {
                "smiles": "Oc1cc2nc3cc(S(=O)(=O)O)ccc3nc2cc1O",
                "names": ["DHPS", "7,8-二羟基吩嗪-2-磺酸", "7,8-dihydroxyphenazine-2-sulfonic acid"],
                "category": "phenazine",
                "redox_potential": -0.85,
                "electrons": 2,
                "solubility_M": 1.8,
                "notes": "高溶解度，负极材料"
            },
            "DHPC": {
                "smiles": "Oc1cc2nc3cc(C(=O)O)ccc3nc2cc1O",
                "names": ["DHPC", "7,8-二羟基吩嗪-2-羧酸", "7,8-dihydroxyphenazine-2-carboxylic acid"],
                "category": "phenazine",
                "redox_potential": -0.82,
                "electrons": 2
            },
            
            # 紫精类 (Viologen)
            "methyl_viologen": {
                "smiles": "C[n+]1ccc(-c2cc[n+](C)cc2)cc1",
                "names": ["甲基紫精", "methyl viologen", "MV", "paraquat"],
                "category": "viologen",
                "redox_potential": -0.45,
                "electrons": 2
            },
            "BTMAP_Vi": {
                "smiles": "C[N+](C)(C)CCCc1cc[n+](Cc2ccc(C[n+]3ccc(-c4cc[n+](CCCN(C)C)cc4)cc3)cc2)cc1",
                "names": ["BTMAP-Vi", "bis(3-trimethylammonio)propyl viologen"],
                "category": "viologen",
                "redox_potential": -0.35,
                "electrons": 2
            },
            
            # 黄素类 (Flavin)
            "alloxazine": {
                "smiles": "O=c1nc2nc3ccccc3nc2c(=O)[nH]1",
                "names": ["咯嗪", "alloxazine", "AZ"],
                "category": "flavin",
                "redox_potential": -0.52,
                "electrons": 2
            },
        }
        
        # 有机活性物质 - 正极材料 (Catholyte)
        self.catholyte_molecules = {
            # TEMPO类
            "TEMPO": {
                "smiles": "CC1(C)CCCC(C)(C)N1[O]",
                "names": ["TEMPO", "2,2,6,6-四甲基哌啶氮氧化物"],
                "category": "nitroxide",
                "redox_potential": 0.80,
                "electrons": 1
            },
            "4-OH-TEMPO": {
                "smiles": "CC1(C)CC(O)CC(C)(C)N1[O]",
                "names": ["4-OH-TEMPO", "4-羟基-TEMPO"],
                "category": "nitroxide",
                "redox_potential": 0.75,
                "electrons": 1
            },
            "TEMPO-sulfate": {
                "smiles": "CC1(C)CC(OS(=O)(=O)O)CC(C)(C)N1[O]",
                "names": ["TEMPO-sulfate", "TEMPO硫酸酯"],
                "category": "nitroxide",
                "redox_potential": 0.82,
                "electrons": 1,
                "solubility_M": 2.0
            },
            
            # 二茂铁类
            "ferrocene": {
                "smiles": "[Fe+2].c1cc[cH-]c1.c1cc[cH-]c1",
                "names": ["二茂铁", "ferrocene", "Fc"],
                "category": "metallocene",
                "redox_potential": 0.40,
                "electrons": 1
            },
            "ferrocyanide": {
                "smiles": "[Fe-4](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
                "names": ["亚铁氰化物", "ferrocyanide", "hexacyanoferrate(II)"],
                "category": "metal_complex",
                "redox_potential": 0.36,
                "electrons": 1
            },
            "ferricyanide": {
                "smiles": "[Fe-3](C#N)(C#N)(C#N)(C#N)(C#N)C#N",
                "names": ["铁氰化物", "ferricyanide", "hexacyanoferrate(III)"],
                "category": "metal_complex",
                "redox_potential": 0.36,
                "electrons": 1
            },
        }
        
        # 无机活性物质（金属离子）
        self.metal_redox_species = {
            # 钒系
            "V2+": {"formula": "V2+", "names": ["二价钒", "V(II)"], "redox_potential": -0.26},
            "V3+": {"formula": "V3+", "names": ["三价钒", "V(III)"], "redox_potential": -0.26},
            "VO2+": {"formula": "VO2+", "names": ["钒氧离子", "V(IV)", "VO2+"], "redox_potential": 1.00},
            "VO2+_ion": {"formula": "VO2+", "names": ["过钒酸根", "V(V)", "VO2+"], "redox_potential": 1.00},
            
            # 铁铬系
            "Fe2+": {"formula": "Fe2+", "names": ["亚铁离子", "Fe(II)"], "redox_potential": 0.77},
            "Fe3+": {"formula": "Fe3+", "names": ["铁离子", "Fe(III)"], "redox_potential": 0.77},
            "Cr2+": {"formula": "Cr2+", "names": ["二价铬", "Cr(II)"], "redox_potential": -0.41},
            "Cr3+": {"formula": "Cr3+", "names": ["三价铬", "Cr(III)"], "redox_potential": -0.41},
            
            # 锌系
            "Zn2+": {"formula": "Zn2+", "names": ["锌离子", "Zn(II)"], "redox_potential": -0.76},
            "Br2/Br-": {"formula": "Br2/Br-", "names": ["溴/溴离子"], "redox_potential": 1.07},
        }
        
        # 支持电解质
        self.supporting_electrolytes = {
            "HCl": {
                "smiles": "Cl",
                "names": ["盐酸", "氯化氢", "hydrochloric acid"],
                "type": "acid"
            },
            "H2SO4": {
                "smiles": "OS(=O)(=O)O",
                "names": ["硫酸", "sulfuric acid"],
                "type": "acid"
            },
            "NaOH": {
                "smiles": "[Na+].[OH-]",
                "names": ["氢氧化钠", "烧碱", "sodium hydroxide"],
                "type": "base"
            },
            "KOH": {
                "smiles": "[K+].[OH-]",
                "names": ["氢氧化钾", "potassium hydroxide"],
                "type": "base"
            },
            "NaCl": {
                "smiles": "[Na+].[Cl-]",
                "names": ["氯化钠", "食盐", "sodium chloride"],
                "type": "salt"
            },
            "KCl": {
                "smiles": "[K+].[Cl-]",
                "names": ["氯化钾", "potassium chloride"],
                "type": "salt"
            },
            "TEABF4": {
                "smiles": "CC[N+](CC)(CC)CC.[B-](F)(F)(F)F",
                "names": ["四乙基四氟硼酸铵", "tetraethylammonium tetrafluoroborate"],
                "type": "salt",
                "system": "non-aqueous"
            },
        }
        
        # 溶剂
        self.solvents = {
            "water": {
                "smiles": "O",
                "names": ["水", "water", "H2O"],
                "type": "protic",
                "dielectric": 80.1
            },
            "acetonitrile": {
                "smiles": "CC#N",
                "names": ["乙腈", "acetonitrile", "MeCN"],
                "type": "aprotic",
                "dielectric": 37.5
            },
            "DMF": {
                "smiles": "CN(C)C=O",
                "names": ["二甲基甲酰胺", "DMF", "dimethylformamide"],
                "type": "aprotic",
                "dielectric": 36.7
            },
            "DMSO": {
                "smiles": "CS(=O)C",
                "names": ["二甲基亚砜", "DMSO", "dimethyl sulfoxide"],
                "type": "aprotic",
                "dielectric": 46.7
            },
            "PC": {
                "smiles": "CC1COC(=O)O1",
                "names": ["碳酸丙烯酯", "PC", "propylene carbonate"],
                "type": "aprotic",
                "dielectric": 64.0
            },
        }
        
        # 常见添加剂
        self.additives = {
            "EDTA": {
                "smiles": "OC(=O)CN(CCN(CC(O)=O)CC(O)=O)CC(O)=O",
                "names": ["EDTA", "乙二胺四乙酸"],
                "function": "complexing agent"
            },
            "citric_acid": {
                "smiles": "OC(=O)CC(O)(CC(O)=O)C(O)=O",
                "names": ["柠檬酸", "citric acid"],
                "function": "complexing agent"
            },
            "oxalic_acid": {
                "smiles": "OC(=O)C(O)=O",
                "names": ["草酸", "oxalic acid"],
                "function": "complexing agent"
            },
            "tartaric_acid": {
                "smiles": "OC(C(O)C(O)=O)C(O)=O",
                "names": ["酒石酸", "tartaric acid"],
                "function": "complexing agent"
            },
        }
        
        # 合并所有分子库用于搜索
        self.all_molecules = {}
        for category_dict in [self.anolyte_molecules, self.catholyte_molecules,
                              self.supporting_electrolytes, self.solvents, self.additives]:
            self.all_molecules.update(category_dict)
    
    def search_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """通过名称搜索分子"""
        name_lower = name.lower().strip()
        
        for mol_id, mol_data in self.all_molecules.items():
            # 检查ID
            if mol_id.lower() == name_lower:
                return {"id": mol_id, **mol_data}
            
            # 检查名称列表
            for mol_name in mol_data.get("names", []):
                if mol_name.lower() == name_lower or name_lower in mol_name.lower():
                    return {"id": mol_id, **mol_data}
        
        # 也搜索金属离子
        for mol_id, mol_data in self.metal_redox_species.items():
            if mol_id.lower() == name_lower:
                return {"id": mol_id, **mol_data, "is_metal_ion": True}
            for mol_name in mol_data.get("names", []):
                if mol_name.lower() == name_lower or name_lower in mol_name.lower():
                    return {"id": mol_id, **mol_data, "is_metal_ion": True}
        
        return None
    
    def get_rfb_context(self, smiles: str) -> Dict[str, Any]:
        """获取分子在液流电池中的应用上下文"""
        context = {
            "is_known_rfb_molecule": False,
            "role": None,
            "category": None,
            "typical_applications": [],
            "related_systems": []
        }
        
        # 在负极材料中搜索
        for mol_id, mol_data in self.anolyte_molecules.items():
            if mol_data.get("smiles") == smiles:
                context.update({
                    "is_known_rfb_molecule": True,
                    "role": "anolyte",
                    "category": mol_data.get("category"),
                    "redox_potential": mol_data.get("redox_potential"),
                    "electrons": mol_data.get("electrons"),
                    "notes": mol_data.get("notes", "")
                })
                return context
        
        # 在正极材料中搜索
        for mol_id, mol_data in self.catholyte_molecules.items():
            if mol_data.get("smiles") == smiles:
                context.update({
                    "is_known_rfb_molecule": True,
                    "role": "catholyte",
                    "category": mol_data.get("category"),
                    "redox_potential": mol_data.get("redox_potential"),
                    "electrons": mol_data.get("electrons")
                })
                return context
        
        return context


# ============================================================================
# 分子性质计算器 (RDKit)
# ============================================================================

class MoleculePropertyCalculator:
    """基于 RDKit 的分子性质计算器"""
    
    def __init__(self):
        self.rdkit_available = False
        self._init_rdkit()
    
    def _init_rdkit(self):
        """初始化 RDKit"""
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, AllChem, rdMolDescriptors
            self.Chem = Chem
            self.Descriptors = Descriptors
            self.AllChem = AllChem
            self.rdMolDescriptors = rdMolDescriptors
            self.rdkit_available = True
            logger.info("✓ RDKit 初始化成功")
        except ImportError:
            logger.warning("⚠️ RDKit 未安装，基础性质计算功能不可用")
            logger.warning("  安装命令: pip install rdkit")
    
    def validate_smiles(self, smiles: str) -> Tuple[bool, Optional[str]]:
        """验证 SMILES 并返回规范化形式"""
        if not self.rdkit_available:
            return False, None
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol is None:
                return False, None
            canonical = self.Chem.MolToSmiles(mol, canonical=True)
            return True, canonical
        except Exception as e:
            logger.error(f"SMILES 验证失败: {e}")
            return False, None
    
    def get_molecule_identifiers(self, smiles: str) -> MoleculeInfo:
        """获取分子的各种标识符"""
        info = MoleculeInfo(identifier=smiles)
        
        if not self.rdkit_available:
            info.error = "RDKit not available"
            return info
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol is None:
                info.error = f"Invalid SMILES: {smiles}"
                return info
            
            info.smiles = smiles
            info.canonical_smiles = self.Chem.MolToSmiles(mol, canonical=True)
            info.inchi = self.Chem.MolToInchi(mol)
            info.inchi_key = self.Chem.MolToInchiKey(mol)
            info.molecular_formula = self.rdMolDescriptors.CalcMolFormula(mol)
            info.is_valid = True
            
        except Exception as e:
            info.error = str(e)
        
        return info
    
    def compute_basic_properties(self, smiles: str) -> List[PropertyResult]:
        """计算基础物化性质"""
        properties = []
        
        if not self.rdkit_available:
            return properties
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol is None:
                return properties
            
            # 分子量
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="molecular_weight",
                value=round(self.Descriptors.MolWt(mol), 2),
                unit="g/mol",
                source="computed"
            ))
            
            # LogP (脂水分配系数)
            properties.append(PropertyResult(
                category=PropertyCategory.SOLUBILITY,
                property_name="logP",
                value=round(self.Descriptors.MolLogP(mol), 2),
                unit="",
                source="computed",
                metadata={"description": "脂水分配系数，值越负越亲水"}
            ))
            
            # TPSA (拓扑极性表面积)
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="TPSA",
                value=round(self.Descriptors.TPSA(mol), 2),
                unit="Å²",
                source="computed",
                metadata={"description": "拓扑极性表面积，影响溶解度和膜渗透性"}
            ))
            
            # 氢键供体/受体数
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_H_donors",
                value=self.Descriptors.NumHDonors(mol),
                unit="",
                source="computed"
            ))
            
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_H_acceptors",
                value=self.Descriptors.NumHAcceptors(mol),
                unit="",
                source="computed"
            ))
            
            # 可旋转键数
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_rotatable_bonds",
                value=self.Descriptors.NumRotatableBonds(mol),
                unit="",
                source="computed"
            ))
            
            # 环数
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_rings",
                value=self.Descriptors.RingCount(mol),
                unit="",
                source="computed"
            ))
            
            # 芳香环数
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_aromatic_rings",
                value=self.rdMolDescriptors.CalcNumAromaticRings(mol),
                unit="",
                source="computed"
            ))
            
            # 形式电荷
            properties.append(PropertyResult(
                category=PropertyCategory.ELECTROCHEMICAL,
                property_name="formal_charge",
                value=self.Chem.GetFormalCharge(mol),
                unit="",
                source="computed"
            ))
            
            # 重原子数
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="num_heavy_atoms",
                value=mol.GetNumHeavyAtoms(),
                unit="",
                source="computed"
            ))
            
            # 摩尔折射率 (与极化率相关)
            properties.append(PropertyResult(
                category=PropertyCategory.BASIC,
                property_name="molar_refractivity",
                value=round(self.Descriptors.MolMR(mol), 2),
                unit="",
                source="computed",
                metadata={"description": "与分子极化率相关"}
            ))
            
        except Exception as e:
            logger.error(f"计算基础性质失败: {e}")
        
        return properties
    
    def compute_electrochemical_descriptors(self, smiles: str) -> List[PropertyResult]:
        """计算与电化学相关的描述符"""
        properties = []
        
        if not self.rdkit_available:
            return properties
        
        try:
            mol = self.Chem.MolFromSmiles(smiles)
            if mol is None:
                return properties
            
            # 判断是否含有氧化还原活性官能团
            redox_groups = self._identify_redox_groups(mol)
            properties.append(PropertyResult(
                category=PropertyCategory.ELECTROCHEMICAL,
                property_name="redox_active_groups",
                value=redox_groups,
                source="computed",
                metadata={"description": "识别的氧化还原活性官能团"}
            ))
            
            # 电子亲和能估计 (基于LUMO能量的近似)
            # 注意：这只是粗略估计，精确值需要DFT计算
            
        except Exception as e:
            logger.error(f"计算电化学描述符失败: {e}")
        
        return properties
    
    def _identify_redox_groups(self, mol) -> List[str]:
        """识别分子中的氧化还原活性官能团"""
        redox_groups = []
        
        smarts_patterns = {
            "quinone": "[#6]1=,:[#6][#6](=O)[#6]=,:[#6][#6]1=O",
            "hydroquinone": "c1cc(O)ccc1O",
            "nitroxide": "[N]([O])(C)(C)",
            "phenazine": "c1ccc2nc3ccccc3nc2c1",
            "viologen": "[n+]1ccc(-c2cc[n+]cc2)cc1",
            "ferrocene": "[Fe]",
            "disulfide": "SS",
            "thiol": "[SH]",
            "nitro": "[N+](=O)[O-]",
            "hydroxyl": "[OH]",
            "carbonyl": "[CX3]=[OX1]",
            "carboxyl": "[CX3](=O)[OX2H1]",
            "amine": "[NX3;H2,H1;!$(NC=O)]",
        }
        
        for name, smarts in smarts_patterns.items():
            try:
                pattern = self.Chem.MolFromSmarts(smarts)
                if pattern and mol.HasSubstructMatch(pattern):
                    redox_groups.append(name)
            except:
                continue
        
        return redox_groups


# ============================================================================
# DeepChem 集成
# ============================================================================

class DeepChemInterface:
    """DeepChem 接口 - MoleculeNet 数据集查询和模型预测"""
    
    def __init__(self, cache_dir: str = None):
        self.deepchem_available = False
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".deepchem_cache")
        self.loaded_datasets = {}
        self.loaded_models = {}
        self._init_deepchem()
    
    def _init_deepchem(self):
        """初始化 DeepChem"""
        try:
            import deepchem as dc
            self.dc = dc
            self.deepchem_available = True
            logger.info("✓ DeepChem 初始化成功")
        except ImportError:
            logger.warning("⚠️ DeepChem 未安装，数据集查询和预测功能不可用")
            logger.warning("  安装命令: pip install deepchem")
    
    def search_in_datasets(self, smiles: str) -> List[Dict[str, Any]]:
        """在 MoleculeNet 数据集中搜索分子"""
        matches = []
        
        if not self.deepchem_available:
            return matches
        
        # 与液流电池相关的数据集
        datasets_to_search = [
            ("delaney", "水溶解度(ESOL)", "log solubility in mols/L"),
            ("lipo", "亲脂性", "octanol/water distribution coefficient"),
            ("freesolv", "水合自由能", "hydration free energy in kcal/mol"),
            ("sampl", "溶解自由能", "solvation free energy"),
            ("bace", "BACE-1抑制活性", "pIC50"),
            ("clintox", "临床毒性", "toxicity"),
            ("tox21", "毒性(Tox21)", "toxicity assays"),
            ("sider", "药物副作用", "side effects"),
        ]
        
        for dataset_name, description, unit in datasets_to_search:
            try:
                match = self._search_single_dataset(dataset_name, smiles)
                if match:
                    match["dataset_description"] = description
                    match["unit"] = unit
                    matches.append(match)
            except Exception as e:
                logger.debug(f"搜索数据集 {dataset_name} 时出错: {e}")
        
        return matches
    
    def _search_single_dataset(self, dataset_name: str, smiles: str) -> Optional[Dict]:
        """在单个数据集中搜索"""
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
                    "transformers": transformers
                }
            except Exception as e:
                logger.warning(f"无法加载数据集 {dataset_name}: {e}")
                return None
        
        dataset_info = self.loaded_datasets[dataset_name]
        
        # 标准化输入SMILES用于比较
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                canonical_smiles = Chem.MolToSmiles(mol, canonical=True)
            else:
                canonical_smiles = smiles
        except:
            canonical_smiles = smiles
        
        # 在所有数据分割中搜索
        for split_name in ["train", "valid", "test"]:
            dataset = dataset_info.get(split_name)
            if dataset is None:
                continue
            
            for i, mol_id in enumerate(dataset.ids):
                try:
                    # 标准化数据集中的SMILES
                    from rdkit import Chem
                    ref_mol = Chem.MolFromSmiles(str(mol_id))
                    if ref_mol:
                        ref_canonical = Chem.MolToSmiles(ref_mol, canonical=True)
                        if canonical_smiles == ref_canonical:
                            return {
                                "dataset": dataset_name,
                                "split": split_name,
                                "tasks": dataset_info["tasks"],
                                "values": dataset.y[i].tolist() if hasattr(dataset.y[i], 'tolist') else list(dataset.y[i]),
                                "matched_smiles": mol_id
                            }
                except:
                    if str(mol_id) == smiles:
                        return {
                            "dataset": dataset_name,
                            "split": split_name,
                            "tasks": dataset_info["tasks"],
                            "values": dataset.y[i].tolist() if hasattr(dataset.y[i], 'tolist') else list(dataset.y[i]),
                            "matched_smiles": mol_id
                        }
        
        return None
    
    def predict_solubility(self, smiles: str) -> Optional[PropertyResult]:
        """使用预训练模型预测溶解度"""
        if not self.deepchem_available:
            return None
        
        try:
            # 加载或获取缓存的模型
            if "solubility" not in self.loaded_models:
                # 使用 ESOL 数据集训练简单模型
                tasks, datasets, transformers = self.dc.molnet.load_delaney(
                    featurizer='GraphConv',
                    data_dir=self.cache_dir
                )
                train_dataset = datasets[0]
                
                model = self.dc.models.GraphConvModel(
                    n_tasks=1,
                    mode='regression',
                    dropout=0.2
                )
                model.fit(train_dataset, nb_epoch=10)
                self.loaded_models["solubility"] = {
                    "model": model,
                    "transformers": transformers
                }
            
            model_info = self.loaded_models["solubility"]
            
            # 特征化输入分子
            featurizer = self.dc.feat.MolGraphConvFeaturizer()
            features = featurizer.featurize([smiles])
            
            # 预测
            prediction = model_info["model"].predict_on_batch(features)
            
            return PropertyResult(
                category=PropertyCategory.SOLUBILITY,
                property_name="predicted_log_solubility",
                value=float(prediction[0][0]),
                unit="log(mol/L)",
                source="predicted",
                confidence=0.7,  # 简单模型的置信度估计
                metadata={"model": "GraphConvModel on ESOL"}
            )
            
        except Exception as e:
            logger.error(f"溶解度预测失败: {e}")
            return None
    
    def predict_toxicity(self, smiles: str) -> List[PropertyResult]:
        """预测毒性相关性质"""
        properties = []
        
        if not self.deepchem_available:
            return properties
        
        # 这里可以添加毒性预测模型
        # 例如使用 Tox21 数据集训练的模型
        
        return properties


# ============================================================================
# 主工具类 - Agent Tool
# ============================================================================

class MoleculePropertyTool:
    """分子性质查询工具 - 供 Agent 调用
    
    整合了：
    1. RFB分子库查询
    2. RDKit 基础性质计算
    3. DeepChem 数据集查询和预测
    """
    
    def __init__(self, 
                 enable_deepchem: bool = True,
                 cache_dir: str = None):
        """初始化分子性质查询工具
        
        Args:
            enable_deepchem: 是否启用 DeepChem 功能
            cache_dir: DeepChem 数据缓存目录
        """
        logger.info("🔬 初始化分子性质查询工具...")
        
        # 初始化各组件
        self.rfb_library = RFBMoleculeLibrary()
        self.calculator = MoleculePropertyCalculator()
        self.deepchem = DeepChemInterface(cache_dir) if enable_deepchem else None
        
        logger.info("✓ 分子性质查询工具初始化完成")
    
    def query(self, 
              identifier: str, 
              query_type: str = "auto",
              include_predictions: bool = True) -> MoleculeQueryResult:
        """执行分子查询 - 主接口
        
        Args:
            identifier: 分子标识符（SMILES、名称或分子式）
            query_type: 查询类型 ("auto", "smiles", "name")
            include_predictions: 是否包含预测性质
            
        Returns:
            MoleculeQueryResult 完整查询结果
        """
        result = MoleculeQueryResult(
            molecule=MoleculeInfo(identifier=identifier)
        )
        
        # Step 1: 解析标识符，获取 SMILES
        smiles = self._resolve_identifier(identifier, query_type, result)
        if not smiles:
            return result
        
        # Step 2: 获取分子基本信息
        result.molecule = self.calculator.get_molecule_identifiers(smiles)
        result.molecule.identifier = identifier
        
        if not result.molecule.is_valid:
            result.errors.append(f"无效的分子: {result.molecule.error}")
            return result
        
        # Step 3: 查询 RFB 分子库上下文
        result.rfb_relevance = self.rfb_library.get_rfb_context(
            result.molecule.canonical_smiles
        )
        
        # Step 4: 计算基础性质 (RDKit)
        result.properties.extend(
            self.calculator.compute_basic_properties(smiles)
        )
        result.properties.extend(
            self.calculator.compute_electrochemical_descriptors(smiles)
        )
        
        # Step 5: 查询 DeepChem 数据集
        if self.deepchem and self.deepchem.deepchem_available:
            result.dataset_matches = self.deepchem.search_in_datasets(smiles)
            
            # Step 6: 预测性质
            if include_predictions:
                sol_pred = self.deepchem.predict_solubility(smiles)
                if sol_pred:
                    result.properties.append(sol_pred)
        
        result.query_success = True
        return result
    
    def _resolve_identifier(self, 
                            identifier: str, 
                            query_type: str,
                            result: MoleculeQueryResult) -> Optional[str]:
        """解析标识符，返回 SMILES"""
        
        # 自动检测类型
        if query_type == "auto":
            # 简单启发式：如果包含特殊字符，可能是 SMILES
            if any(c in identifier for c in ['=', '#', '(', ')', '[', ']', '@', '+', '-', '/', '\\']):
                query_type = "smiles"
            else:
                query_type = "name"
        
        if query_type == "smiles":
            # 验证 SMILES
            is_valid, canonical = self.calculator.validate_smiles(identifier)
            if is_valid:
                return canonical or identifier
            else:
                result.errors.append(f"无效的 SMILES: {identifier}")
                return None
        
        elif query_type == "name":
            # 首先在 RFB 分子库中查找
            mol_data = self.rfb_library.search_by_name(identifier)
            if mol_data:
                smiles = mol_data.get("smiles")
                if smiles:
                    result.molecule.common_names = mol_data.get("names", [])
                    return smiles
            
            # 如果没找到，尝试使用 PubChem API (需要网络)
            # TODO: 添加 PubChem 查询
            
            result.errors.append(f"未找到分子: {identifier}")
            return None
        
        return None
    
    def get_tool_description(self) -> str:
        """返回工具描述，供 Agent 使用"""
        return """
分子性质查询工具 (MoleculePropertyTool)

功能：查询分子的物化性质、电化学特性以及在科学数据集中的已有数据

适用场景：
- 用户询问某种分子/化合物的性质
- 需要了解液流电池电解质组分的物化参数
- 评估活性物质的溶解度、氧化还原电位等
- 比较不同分子的性质
- 查询分子在液流电池中的应用角色

输入参数：
- identifier: 分子的 SMILES 字符串、中文名称或英文名称
- query_type: "auto"(自动检测), "smiles", "name"
- include_predictions: 是否包含预测性质

输出内容：
- 分子基本信息（分子式、InChI等）
- 基础物化性质（分子量、LogP、极性表面积等）
- 电化学相关描述符（氧化还原活性官能团等）
- 液流电池应用上下文（正极/负极材料、类别等）
- MoleculeNet 数据集匹配记录
- 预测性质（溶解度等）

示例查询：
- query("DHPS")
- query("蒽醌")
- query("c1ccc2nc3ccccc3nc2c1", query_type="smiles")
"""
    
    def format_result_for_context(self, result: MoleculeQueryResult) -> str:
        """格式化结果为上下文字符串，用于 RAG 融合"""
        if not result.query_success:
            return f"分子查询失败: {'; '.join(result.errors)}"
        
        lines = []
        mol = result.molecule
        
        # 基本信息
        lines.append(f"=== 分子: {mol.identifier} ===")
        if mol.molecular_formula:
            lines.append(f"分子式: {mol.molecular_formula}")
        if mol.canonical_smiles:
            lines.append(f"SMILES: {mol.canonical_smiles}")
        
        # RFB 上下文
        rfb = result.rfb_relevance
        if rfb.get("is_known_rfb_molecule"):
            lines.append(f"\n液流电池应用:")
            lines.append(f"  - 角色: {rfb.get('role', 'N/A')}")
            lines.append(f"  - 类别: {rfb.get('category', 'N/A')}")
            if rfb.get("redox_potential"):
                lines.append(f"  - 氧化还原电位: {rfb['redox_potential']} V vs SHE")
            if rfb.get("electrons"):
                lines.append(f"  - 电子转移数: {rfb['electrons']}")
        
        # 基础性质
        lines.append(f"\n物化性质:")
        for prop in result.properties:
            if prop.category == PropertyCategory.BASIC:
                unit_str = f" {prop.unit}" if prop.unit else ""
                lines.append(f"  - {prop.property_name}: {prop.value}{unit_str}")
        
        # 溶解度相关
        sol_props = [p for p in result.properties if p.category == PropertyCategory.SOLUBILITY]
        if sol_props:
            lines.append(f"\n溶解度相关:")
            for prop in sol_props:
                source_str = f" ({prop.source})" if prop.source != "computed" else ""
                lines.append(f"  - {prop.property_name}: {prop.value}{source_str}")
        
        # 电化学描述符
        echem_props = [p for p in result.properties if p.category == PropertyCategory.ELECTROCHEMICAL]
        if echem_props:
            lines.append(f"\n电化学特性:")
            for prop in echem_props:
                lines.append(f"  - {prop.property_name}: {prop.value}")
        
        # 数据集匹配
        if result.dataset_matches:
            lines.append(f"\nMoleculeNet 数据集记录:")
            for match in result.dataset_matches:
                lines.append(f"  - {match['dataset']} ({match.get('dataset_description', '')}):")
                for task, value in zip(match['tasks'], match['values']):
                    lines.append(f"      {task}: {value}")
        
        return "\n".join(lines)


# ============================================================================
# Agent 集成辅助类
# ============================================================================

class MoleculeQueryAgent:
    """分子查询 Agent - 与现有 RAG 系统集成
    
    可以作为一个独立的 Agent，也可以作为工具集成到现有的 Agent 框架中
    """
    
    def __init__(self, 
                 llm_config=None,
                 enable_deepchem: bool = True):
        """初始化
        
        Args:
            llm_config: LLMConfig 实例（用于从问题中提取分子名称）
            enable_deepchem: 是否启用 DeepChem
        """
        self.llm = llm_config
        self.tool = MoleculePropertyTool(enable_deepchem=enable_deepchem)
        
        # 触发关键词
        self.trigger_keywords = [
            "性质", "溶解度", "分子量", "电位", "氧化还原",
            "结构", "官能团", "LogP", "SMILES",
            "property", "solubility", "molecular weight",
        ]
        
        # 分子类型关键词
        self.molecule_keywords = [
            "分子", "化合物", "物质", "材料", "电解质",
            "molecule", "compound", "material",
        ]
    
    def should_query(self, question: str) -> bool:
        """判断是否需要进行分子查询"""
        question_lower = question.lower()
        
        # 检查是否包含触发关键词
        has_trigger = any(kw in question_lower for kw in self.trigger_keywords)
        has_molecule_ref = any(kw in question_lower for kw in self.molecule_keywords)
        
        # 检查是否包含已知的分子名称
        has_known_molecule = self._contains_known_molecule(question)
        
        return (has_trigger and has_molecule_ref) or has_known_molecule
    
    def _contains_known_molecule(self, question: str) -> bool:
        """检查问题中是否包含已知分子"""
        question_lower = question.lower()
        
        # 检查 RFB 分子库中的所有分子名称
        for mol_data in self.tool.rfb_library.all_molecules.values():
            for name in mol_data.get("names", []):
                if name.lower() in question_lower:
                    return True
        
        return False
    
    def extract_molecules_from_question(self, question: str) -> List[str]:
        """从问题中提取分子名称/SMILES
        
        如果有 LLM，使用 LLM 提取；否则使用规则
        """
        molecules = []
        question_lower = question.lower()
        
        # 方法1: 检查 RFB 分子库
        for mol_id, mol_data in self.tool.rfb_library.all_molecules.items():
            for name in mol_data.get("names", []):
                if name.lower() in question_lower:
                    molecules.append(name)
                    break
        
        # 方法2: 如果有 LLM，使用 LLM 提取更多
        if self.llm and not molecules:
            prompt = f"""从以下问题中提取所有提到的化学分子、化合物名称或SMILES字符串。
仅返回名称列表，用逗号分隔。如果没有找到，返回"无"。

问题：{question}

分子列表："""
            
            response = self.llm.call_llm(prompt, temperature=0.0, max_tokens=200)
            if response and "无" not in response and "❌" not in response:
                extracted = [m.strip() for m in response.split(",") if m.strip()]
                molecules.extend(extracted)
        
        return list(set(molecules))  # 去重
    
    def process_query(self, question: str) -> Tuple[str, List[MoleculeQueryResult]]:
        """处理分子相关查询
        
        Returns:
            (格式化的上下文字符串, 原始结果列表)
        """
        # 提取分子
        molecules = self.extract_molecules_from_question(question)
        
        if not molecules:
            return "", []
        
        # 查询每个分子
        results = []
        context_parts = []
        
        for mol in molecules:
            result = self.tool.query(mol)
            results.append(result)
            
            if result.query_success:
                context_parts.append(self.tool.format_result_for_context(result))
        
        combined_context = "\n\n".join(context_parts)
        return combined_context, results


# ============================================================================
# 与 KnowledgeArsenal 集成
# ============================================================================

def integrate_with_arsenal(arsenal, enable_deepchem: bool = True):
    """将分子查询工具集成到现有的 KnowledgeArsenal
    
    Args:
        arsenal: KnowledgeArsenal 实例
        enable_deepchem: 是否启用 DeepChem
        
    Returns:
        MoleculeQueryAgent 实例
    """
    llm = arsenal.get_llm() if hasattr(arsenal, 'get_llm') else None
    agent = MoleculeQueryAgent(llm_config=llm, enable_deepchem=enable_deepchem)
    
    # 将 agent 附加到 arsenal
    arsenal.molecule_agent = agent
    
    logger.info("✓ 分子查询工具已集成到 KnowledgeArsenal")
    return agent


# ============================================================================
# 测试和演示
# ============================================================================

def demo():
    """演示分子查询工具的使用"""
    print("\n" + "="*80)
    print("🔬 分子性质查询工具演示")
    print("="*80 + "\n")
    
    # 初始化工具（不启用 DeepChem 以加快测试）
    tool = MoleculePropertyTool(enable_deepchem=False)
    
    # 测试查询
    test_queries = [
        ("DHPS", "name"),           # 液流电池负极材料
        ("TEMPO", "name"),          # 液流电池正极材料
        ("蒽醌", "name"),           # 中文名称
        ("ferrocyanide", "name"),   # 铁氰化物
        ("c1ccc2nc3ccccc3nc2c1", "smiles"),  # 吩嗪 SMILES
        ("phenazine", "name"), 
    ]
    
    for identifier, query_type in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {identifier} (类型: {query_type})")
        print('='*60)
        
        result = tool.query(identifier, query_type=query_type)
        
        if result.query_success:
            print(tool.format_result_for_context(result))
        else:
            print(f"❌ 查询失败: {result.errors}")
    
    print("\n" + "="*80)
    print("演示完成")
    print("="*80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        print("""
分子性质查询工具使用说明：

1. 独立使用:
   from molecule_property_tool import MoleculePropertyTool
   
   tool = MoleculePropertyTool()
   result = tool.query("DHPS")
   print(tool.format_result_for_context(result))

2. 与 KnowledgeArsenal 集成:
   from molecule_property_tool import integrate_with_arsenal
   
   arsenal = KnowledgeArsenal()
   mol_agent = integrate_with_arsenal(arsenal)
   
   # 查询
   context, results = mol_agent.process_query("DHPS的溶解度是多少？")

3. 运行演示:
   python molecule_property_tool.py --demo

4. 支持的查询方式:
   - 分子名称 (中英文): "蒽醌", "TEMPO", "ferrocyanide"
   - SMILES: "c1ccc2nc3ccccc3nc2c1"
   - 自动检测: tool.query("某个标识符", query_type="auto")
""")
