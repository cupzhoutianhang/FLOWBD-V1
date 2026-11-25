#!/usr/bin/env python3
"""
知识图谱提取结果自动检查与修复工具
用于检查液流电池领域实体和关系提取的质量，生成修正建议返回给大模型
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# ==================== 配置定义 ====================

VALID_ENTITY_TYPES = {
    "Material", "Species", "Property", "Value", "Condition",
    "Reaction", "Mechanism", "Component", "Method", "Device",
    "FunctionalGroup", "Catalyst"
}

VALID_RELATION_TYPES = {
    # 性能关系
    "HAS_PROPERTY", "HAS_VALUE", "MEASURED_AT",
    # 结构关系
    "DERIVED_FROM", "HAS_FUNCTIONAL_GROUP", "CONTAINS", "USED_AS", "PAIRED_WITH",
    # 合成/制备关系
    "SYNTHESIZED_FROM", "PRODUCT", "SYNTHESIS_YIELD", "MODIFIED_BY",
    # 因果关系
    "IMPROVES", "REDUCES", "CAUSES", "PREVENTS", "ENABLES",
    # 反应机理关系
    "REACTANT", "INVOLVES", "CATALYZED_BY", "OCCURS_AT",
    # 表征关系
    "CHARACTERIZED_BY"
}

# 关系的合法source/target类型约束
RELATION_TYPE_CONSTRAINTS = {
    "HAS_PROPERTY": {
        "source": {"Material", "Device", "Reaction", "Component"},
        "target": {"Property"}
    },
    "HAS_VALUE": {
        "source": {"Property"},
        "target": {"Value"}
    },
    "MEASURED_AT": {
        "source": {"Property"},
        "target": {"Condition"}
    },
    "DERIVED_FROM": {
        "source": {"Material"},
        "target": {"Material"}
    },
    "HAS_FUNCTIONAL_GROUP": {
        "source": {"Material"},
        "target": {"FunctionalGroup"}
    },
    "CONTAINS": {
        "source": {"Device", "Component"},
        "target": {"Component", "Material"}
    },
    "USED_AS": {
        "source": {"Material"},
        "target": {"Component"}
    },
    "PAIRED_WITH": {
        "source": {"Material"},
        "target": {"Material"}
    },
    "SYNTHESIZED_FROM": {
        "source": {"Material"},
        "target": {"Material"}
    },
    "PRODUCT": {
        "source": {"Reaction"},
        "target": {"Material", "Species"}
    },
    "REACTANT": {
        "source": {"Reaction"},
        "target": {"Material", "Species"}
    },
    "INVOLVES": {
        "source": {"Reaction", "Mechanism"},
        "target": {"Species", "Reaction"}
    },
    "CATALYZED_BY": {
        "source": {"Reaction"},
        "target": {"Catalyst"}
    },
    "OCCURS_AT": {
        "source": {"Reaction"},
        "target": {"Component"}
    },
    "IMPROVES": {
        "source": VALID_ENTITY_TYPES,  # 任意类型
        "target": {"Property"}
    },
    "REDUCES": {
        "source": VALID_ENTITY_TYPES,
        "target": {"Property"}
    },
    "CAUSES": {
        "source": VALID_ENTITY_TYPES,
        "target": {"Property"}
    },
    "PREVENTS": {
        "source": VALID_ENTITY_TYPES,
        "target": {"Property"}
    },
    "ENABLES": {
        "source": VALID_ENTITY_TYPES,
        "target": {"Property"}
    },
    "CHARACTERIZED_BY": {
        "source": {"Material", "Property"},
        "target": {"Method"}
    },
    "SYNTHESIS_YIELD": {
        "source": {"Reaction"},
        "target": {"Value"}
    },
    "MODIFIED_BY": {
        "source": {"Material"},
        "target": {"Method"}
    }
}

ID_PREFIX_MAP = {
    "Material": "m",
    "Species": "sp",
    "Property": "p",
    "Value": "v",
    "Condition": "c",
    "Reaction": "r",
    "Mechanism": "mech",
    "Component": "comp",
    "Method": "met",
    "Device": "d",
    "FunctionalGroup": "fg",
    "Catalyst": "cat"
}


# ==================== 数据类定义 ====================

class IssueSeverity(Enum):
    ERROR = "ERROR"      # 严重错误，必须修复
    WARNING = "WARNING"  # 警告，建议修复
    INFO = "INFO"        # 提示，可选修复


@dataclass
class Issue:
    """检查发现的问题"""
    severity: IssueSeverity
    category: str
    message: str
    entity_id: str = None
    relation_index: int = None
    suggestion: str = None


@dataclass
class CheckResult:
    """检查结果汇总"""
    issues: List[Issue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def add_issue(self, severity: IssueSeverity, category: str, message: str, 
                  entity_id: str = None, relation_index: int = None, suggestion: str = None):
        self.issues.append(Issue(severity, category, message, entity_id, relation_index, suggestion))
    
    def get_errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]
    
    def get_warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]
    
    def get_infos(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == IssueSeverity.INFO]


# ==================== 检查器类 ====================

class KnowledgeGraphChecker:
    """知识图谱提取结果检查器"""

    @staticmethod
    def _normalize_entity(e: dict) -> dict:
        """修复 LLM 偶发的格式错误：{"p9": "Property", "name": "..."} → {"id": "p9", "type": "Property", "name": "..."}"""
        if "id" in e:
            return e
        for key, val in e.items():
            if key not in ("name", "type", "properties") and isinstance(val, str) and val in VALID_ENTITY_TYPES:
                normalized = {"id": key, "type": val}
                normalized.update({k: v for k, v in e.items() if k != key})
                return normalized
        return e  # 无法修复时原样返回，后续 if "id" in e 会跳过

    def __init__(self, kg_data: Dict, markdown_content: str = None):
        """
        初始化检查器
        
        Args:
            kg_data: 提取的知识图谱数据，包含entities和relations
            markdown_content: 原始文献的markdown内容（可选，用于深度检查）
        """
        self.data = kg_data.get("data", kg_data)
        raw_entities = [self._normalize_entity(e) for e in self.data.get("entities", [])]
        self.entities = {e["id"]: e for e in raw_entities if "id" in e}
        self.relations = self.data.get("relations", [])
        self.markdown = markdown_content or ""
        self.result = CheckResult()
        
    def run_all_checks(self) -> CheckResult:
        """运行所有检查"""
        self._check_entity_basics()
        self._check_entity_duplicates()
        self._check_id_naming()
        self._check_relation_validity()
        self._check_relation_type_constraints()
        self._check_orphan_entities()
        self._check_property_value_chain()
        self._check_reaction_completeness()
        self._check_derived_from_relations()
        self._check_value_units()
        self._check_property_specificity()
        self._compute_statistics()
        
        if self.markdown:
            self._check_missing_key_entities()
        
        return self.result
    
    def _check_entity_basics(self):
        """检查实体基本格式"""
        for eid, entity in self.entities.items():
            # 检查必需字段
            if "type" not in entity:
                self.result.add_issue(
                    IssueSeverity.ERROR, "entity_format",
                    f"实体 {eid} 缺少 type 字段",
                    entity_id=eid,
                    suggestion="添加正确的type字段"
                )
            elif entity["type"] not in VALID_ENTITY_TYPES:
                self.result.add_issue(
                    IssueSeverity.ERROR, "entity_type",
                    f"实体 {eid} 的type '{entity['type']}' 不在有效类型列表中",
                    entity_id=eid,
                    suggestion=f"type应为以下之一: {', '.join(VALID_ENTITY_TYPES)}"
                )
            
            if "name" not in entity:
                self.result.add_issue(
                    IssueSeverity.ERROR, "entity_format",
                    f"实体 {eid} 缺少 name 字段",
                    entity_id=eid
                )
            elif not entity["name"].strip():
                self.result.add_issue(
                    IssueSeverity.ERROR, "entity_format",
                    f"实体 {eid} 的 name 为空",
                    entity_id=eid
                )
    
    def _check_entity_duplicates(self):
        """检查实体重复"""
        name_to_ids = defaultdict(list)
        normalized_names = {}
        
        for eid, entity in self.entities.items():
            name = entity.get("name", "")
            name_to_ids[name].append(eid)
            
            # 标准化名称（去除空格、转小写）
            normalized = re.sub(r'\s+', '', name.lower())
            if normalized in normalized_names:
                self.result.add_issue(
                    IssueSeverity.WARNING, "duplicate_entity",
                    f"实体 {eid} ({name}) 可能与 {normalized_names[normalized]} 重复",
                    entity_id=eid,
                    suggestion="检查是否为同一实体的不同表示，如缩写与全称"
                )
            else:
                normalized_names[normalized] = eid
        
        # 检查完全相同的名称
        for name, ids in name_to_ids.items():
            if len(ids) > 1:
                self.result.add_issue(
                    IssueSeverity.ERROR, "duplicate_entity",
                    f"发现重复实体名称 '{name}': {', '.join(ids)}",
                    suggestion="合并重复实体或区分命名"
                )
        
        # 特别检查缩写和全称的对应关系
        self._check_abbreviation_duplicates()
    
    def _check_abbreviation_duplicates(self):
        """检查缩写与全称的重复"""
        # 常见的缩写映射
        abbreviation_patterns = [
            (r'DHPS', r'7,8-dihydroxyphenazine-2-sulfonic acid'),
            (r'DHPC', r'7,8-dihydroxyphenazine-2-carboxylic acid'),
            (r'DHP', r'2,3-dihydroxyphenazine'),
        ]
        
        entity_names = {e.get("name", ""): eid for eid, e in self.entities.items()}
        
        for abbr, full in abbreviation_patterns:
            abbr_ids = [eid for name, eid in entity_names.items() if re.search(abbr, name, re.I)]
            full_ids = [eid for name, eid in entity_names.items() if re.search(full, name, re.I)]
            
            if abbr_ids and full_ids:
                self.result.add_issue(
                    IssueSeverity.WARNING, "abbreviation_duplicate",
                    f"缩写 '{abbr}' ({abbr_ids}) 和全称 '{full}' ({full_ids}) 可能指同一实体",
                    suggestion="保留一个实体，删除重复项，或确保它们确实不同"
                )
    
    def _check_id_naming(self):
        """检查ID命名规范"""
        for eid, entity in self.entities.items():
            etype = entity.get("type", "")
            if etype in ID_PREFIX_MAP:
                expected_prefix = ID_PREFIX_MAP[etype]
                if not eid.startswith(expected_prefix):
                    self.result.add_issue(
                        IssueSeverity.WARNING, "id_naming",
                        f"实体 {eid} (类型 {etype}) 的ID应以 '{expected_prefix}' 开头",
                        entity_id=eid,
                        suggestion=f"建议将ID改为 {expected_prefix}X 格式"
                    )
    
    def _check_relation_validity(self):
        """检查关系基本有效性"""
        for idx, rel in enumerate(self.relations):
            source = rel.get("source")
            target = rel.get("target")
            relation = rel.get("relation")
            
            # 检查必需字段
            if not source or not target or not relation:
                self.result.add_issue(
                    IssueSeverity.ERROR, "relation_format",
                    f"关系 #{idx} 缺少必需字段: source/target/relation",
                    relation_index=idx
                )
                continue
            
            # 检查source是否存在
            if source not in self.entities:
                self.result.add_issue(
                    IssueSeverity.ERROR, "invalid_reference",
                    f"关系 #{idx} 的source '{source}' 不存在于实体列表中",
                    relation_index=idx,
                    suggestion="确保source引用已存在的实体ID"
                )
            
            # 检查target是否存在
            if target not in self.entities:
                self.result.add_issue(
                    IssueSeverity.ERROR, "invalid_reference",
                    f"关系 #{idx} 的target '{target}' 不存在于实体列表中",
                    relation_index=idx,
                    suggestion="确保target引用已存在的实体ID"
                )
            
            # 检查关系类型是否有效
            if relation not in VALID_RELATION_TYPES:
                self.result.add_issue(
                    IssueSeverity.ERROR, "invalid_relation_type",
                    f"关系 #{idx} 的类型 '{relation}' 不在有效关系类型列表中",
                    relation_index=idx,
                    suggestion=f"关系类型应为以下之一: {', '.join(VALID_RELATION_TYPES)}"
                )
    
    def _check_relation_type_constraints(self):
        """检查关系的类型约束"""
        for idx, rel in enumerate(self.relations):
            source_id = rel.get("source")
            target_id = rel.get("target")
            relation = rel.get("relation")
            
            if source_id not in self.entities or target_id not in self.entities:
                continue  # 已在上一步检查
            
            if relation not in RELATION_TYPE_CONSTRAINTS:
                continue  # 未定义约束或已在上一步检查
            
            source_type = self.entities[source_id].get("type")
            target_type = self.entities[target_id].get("type")
            constraints = RELATION_TYPE_CONSTRAINTS[relation]
            
            if source_type not in constraints["source"]:
                self.result.add_issue(
                    IssueSeverity.ERROR, "type_constraint",
                    f"关系 #{idx}: {relation} 的source类型应为 {constraints['source']}，但实际是 {source_type}",
                    relation_index=idx,
                    suggestion=f"检查实体 {source_id} 的类型是否正确，或更换关系类型"
                )
            
            if target_type not in constraints["target"]:
                self.result.add_issue(
                    IssueSeverity.ERROR, "type_constraint",
                    f"关系 #{idx}: {relation} 的target类型应为 {constraints['target']}，但实际是 {target_type}",
                    relation_index=idx,
                    suggestion=f"检查实体 {target_id} 的类型是否正确，或更换关系类型"
                )
    
    def _check_orphan_entities(self):
        """检查孤立实体（没有任何关系指向或来自它）"""
        connected_entities = set()
        
        for rel in self.relations:
            connected_entities.add(rel.get("source"))
            connected_entities.add(rel.get("target"))
        
        orphans = set(self.entities.keys()) - connected_entities
        
        for eid in orphans:
            entity = self.entities[eid]
            self.result.add_issue(
                IssueSeverity.WARNING, "orphan_entity",
                f"实体 {eid} ({entity.get('name')}) 没有任何关系连接",
                entity_id=eid,
                suggestion="为该实体添加适当的关系，或确认是否需要保留"
            )
    
    def _check_property_value_chain(self):
        """检查Property → Value → Condition链的完整性"""
        # 收集所有Property
        properties = {eid: e for eid, e in self.entities.items() if e.get("type") == "Property"}
        
        # 收集Property的HAS_VALUE和MEASURED_AT关系
        property_has_value = defaultdict(list)
        property_measured_at = defaultdict(list)
        
        for rel in self.relations:
            if rel.get("relation") == "HAS_VALUE" and rel.get("source") in properties:
                property_has_value[rel["source"]].append(rel["target"])
            if rel.get("relation") == "MEASURED_AT" and rel.get("source") in properties:
                property_measured_at[rel["source"]].append(rel["target"])
        
        for pid, prop in properties.items():
            prop_name = prop.get("name", "")
            
            # 检查是否有HAS_VALUE
            if pid not in property_has_value:
                self.result.add_issue(
                    IssueSeverity.WARNING, "incomplete_chain",
                    f"Property {pid} ({prop_name}) 没有 HAS_VALUE 关系",
                    entity_id=pid,
                    suggestion="添加 (Property, HAS_VALUE, Value) 关系"
                )
            
            # 检查是否有MEASURED_AT（对于需要条件的Property）
            # 判断是否需要条件：名称中包含条件描述的Property可能不需要额外的MEASURED_AT
            has_condition_in_name = bool(re.search(r'\(.*?[MmV°C%]\.*?\)', prop_name))
            if pid not in property_measured_at and not has_condition_in_name:
                self.result.add_issue(
                    IssueSeverity.INFO, "missing_condition",
                    f"Property {pid} ({prop_name}) 没有 MEASURED_AT 关系",
                    entity_id=pid,
                    suggestion="如果有测量条件，添加 (Property, MEASURED_AT, Condition) 关系"
                )
    
    def _check_reaction_completeness(self):
        """检查Reaction的完整性（REACTANT, PRODUCT, INVOLVES）"""
        reactions = {eid: e for eid, e in self.entities.items() if e.get("type") == "Reaction"}
        
        reaction_reactants = defaultdict(list)
        reaction_products = defaultdict(list)
        reaction_involves = defaultdict(list)
        
        for rel in self.relations:
            source = rel.get("source")
            if source in reactions:
                if rel.get("relation") == "REACTANT":
                    reaction_reactants[source].append(rel["target"])
                elif rel.get("relation") == "PRODUCT":
                    reaction_products[source].append(rel["target"])
                elif rel.get("relation") == "INVOLVES":
                    reaction_involves[source].append(rel["target"])
        
        for rid, reaction in reactions.items():
            rxn_name = reaction.get("name", "")
            
            if rid not in reaction_reactants:
                self.result.add_issue(
                    IssueSeverity.WARNING, "incomplete_reaction",
                    f"Reaction {rid} ({rxn_name}) 没有 REACTANT 关系",
                    entity_id=rid,
                    suggestion="添加 (Reaction, REACTANT, Species/Material) 关系"
                )
            
            if rid not in reaction_products:
                self.result.add_issue(
                    IssueSeverity.WARNING, "incomplete_reaction",
                    f"Reaction {rid} ({rxn_name}) 没有 PRODUCT 关系",
                    entity_id=rid,
                    suggestion="添加 (Reaction, PRODUCT, Species/Material) 关系"
                )
            
            # 检查是否涉及电子转移
            if rid not in reaction_involves:
                self.result.add_issue(
                    IssueSeverity.INFO, "missing_involves",
                    f"Reaction {rid} ({rxn_name}) 没有 INVOLVES 关系",
                    entity_id=rid,
                    suggestion="如果反应涉及电子或质子转移，添加 INVOLVES 关系"
                )
    
    def _check_derived_from_relations(self):
        """检查衍生物关系"""
        # 在液流电池文献中，衍生物关系很重要
        materials = {eid: e for eid, e in self.entities.items() if e.get("type") == "Material"}
        
        has_derived_from = set()
        derived_from_targets = set()
        
        for rel in self.relations:
            if rel.get("relation") == "DERIVED_FROM":
                has_derived_from.add(rel["source"])
                derived_from_targets.add(rel["target"])
        
        # 检查可能的衍生物但没有DERIVED_FROM关系
        derivative_patterns = [
            r'derivative', r'衍生物', r'-based', r'modified', r'functionalized'
        ]
        
        for mid, mat in materials.items():
            name = mat.get("name", "")
            for pattern in derivative_patterns:
                if re.search(pattern, name, re.I) and mid not in has_derived_from:
                    self.result.add_issue(
                        IssueSeverity.INFO, "missing_derived_from",
                        f"Material {mid} ({name}) 名称暗示是衍生物，但没有 DERIVED_FROM 关系",
                        entity_id=mid,
                        suggestion="检查是否需要添加 DERIVED_FROM 关系"
                    )
    
    def _check_value_units(self):
        """检查Value是否包含单位"""
        values = {eid: e for eid, e in self.entities.items() if e.get("type") == "Value"}
        
        # 常见单位模式
        unit_patterns = [
            r'[MmμnpkKG]?[VvAaWwJjLl]',  # V, mV, A, mA, W, L等
            r'%',
            r'°[CFK]',
            r'mol|M\b',
            r'cm|mm|nm|μm',
            r'Hz|kHz|MHz',
            r's\b|min|h\b|day',
            r'cycle',
            r'ppm',
            r'Ah|Wh',
            r'ohm|Ω',
        ]
        unit_regex = '|'.join(unit_patterns)
        
        for vid, val in values.items():
            name = val.get("name", "")
            if not re.search(unit_regex, name, re.I) and not re.search(r'^\s*[<>≤≥]?\s*[\d.]+\s*$', name):
                # 纯数字且没有单位
                self.result.add_issue(
                    IssueSeverity.WARNING, "missing_unit",
                    f"Value {vid} ({name}) 可能缺少单位",
                    entity_id=vid,
                    suggestion="Value应包含数值和单位，如 '1.8 M' 或 '99%'"
                )
    
    def _check_property_specificity(self):
        """检查Property命名是否足够具体"""
        properties = {eid: e for eid, e in self.entities.items() if e.get("type") == "Property"}
        
        generic_names = [
            '溶解度', '效率', '容量', '电位', '电压', '电流', '功率',
            'solubility', 'efficiency', 'capacity', 'potential', 'voltage', 'current', 'power'
        ]
        
        for pid, prop in properties.items():
            name = prop.get("name", "")
            for generic in generic_names:
                if name.lower() == generic.lower():
                    self.result.add_issue(
                        IssueSeverity.WARNING, "generic_property",
                        f"Property {pid} ({name}) 名称过于笼统",
                        entity_id=pid,
                        suggestion="Property应具体命名，如 'DHPS溶解度(1M KOH)' 而非 '溶解度'"
                    )
    
    def _check_missing_key_entities(self):
        """基于原文检查是否遗漏关键实体"""
        if not self.markdown:
            return
        
        # 关键词检测
        keywords_to_check = {
            "Material": [
                r'phenazine', r'DHPS', r'DHPC', r'DHP', r'ferro.?cyanide', r'ferri.?cyanide',
                r'Nafion', r'NaOH', r'KOH', r'LiOH', r'benzoquinone', r'diaminobenzene'
            ],
            "Species": [r'e⁻|electron', r'H⁺|proton', r'Na⁺', r'K⁺', r'Li⁺', r'Fe\(CN\)'],
            "Value": [r'\d+\.?\d*\s*[MmV%]', r'\d+\.?\d*\s*mA.?cm', r'\d+\.?\d*\s*Ah'],
            "Property": [r'solubility|溶解度', r'efficiency|效率', r'capacity|容量', r'potential|电位'],
            "Method": [r'CV|cyclic voltamm', r'NMR', r'DFT', r'UV-vis', r'ESI-MS'],
        }
        
        existing_names = {e.get("name", "").lower() for e in self.entities.values()}
        
        for etype, patterns in keywords_to_check.items():
            for pattern in patterns:
                matches = re.findall(pattern, self.markdown, re.I)
                for match in set(matches):
                    if match.lower() not in existing_names:
                        # 简单的模糊匹配
                        found = any(match.lower() in name for name in existing_names)
                        if not found:
                            self.result.add_issue(
                                IssueSeverity.INFO, "potentially_missing",
                                f"原文中出现 '{match}' 可能需要提取为 {etype}",
                                suggestion=f"检查是否需要添加此实体"
                            )
    
    def _compute_statistics(self):
        """计算统计信息"""
        type_counts = defaultdict(int)
        for entity in self.entities.values():
            type_counts[entity.get("type", "Unknown")] += 1
        
        relation_counts = defaultdict(int)
        for rel in self.relations:
            relation_counts[rel.get("relation", "Unknown")] += 1
        
        self.result.stats = {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entity_type_distribution": dict(type_counts),
            "relation_type_distribution": dict(relation_counts),
            "error_count": len(self.result.get_errors()),
            "warning_count": len(self.result.get_warnings()),
            "info_count": len(self.result.get_infos())
        }


# ==================== 报告生成器 ====================

class ReportGenerator:
    """生成检查报告和修复Prompt"""
    
    def __init__(self, result: CheckResult, kg_data: Dict, markdown_content: str = None):
        self.result = result
        self.kg_data = kg_data
        self.markdown = markdown_content
    
    def generate_summary_report(self) -> str:
        """生成摘要报告"""
        lines = ["# 知识图谱提取质量检查报告\n"]
        
        # 统计信息
        stats = self.result.stats
        lines.append("## 统计概览\n")
        lines.append(f"- 实体总数: {stats.get('total_entities', 0)}")
        lines.append(f"- 关系总数: {stats.get('total_relations', 0)}")
        lines.append(f"- 错误数: {stats.get('error_count', 0)}")
        lines.append(f"- 警告数: {stats.get('warning_count', 0)}")
        lines.append(f"- 提示数: {stats.get('info_count', 0)}")
        
        lines.append("\n### 实体类型分布")
        for etype, count in stats.get('entity_type_distribution', {}).items():
            lines.append(f"- {etype}: {count}")
        
        lines.append("\n### 关系类型分布")
        for rtype, count in stats.get('relation_type_distribution', {}).items():
            lines.append(f"- {rtype}: {count}")
        
        # 问题列表
        if self.result.get_errors():
            lines.append("\n## ❌ 错误 (必须修复)\n")
            for issue in self.result.get_errors():
                lines.append(f"- **[{issue.category}]** {issue.message}")
                if issue.suggestion:
                    lines.append(f"  - 建议: {issue.suggestion}")
        
        if self.result.get_warnings():
            lines.append("\n## ⚠️ 警告 (建议修复)\n")
            for issue in self.result.get_warnings():
                lines.append(f"- **[{issue.category}]** {issue.message}")
                if issue.suggestion:
                    lines.append(f"  - 建议: {issue.suggestion}")
        
        if self.result.get_infos():
            lines.append("\n## ℹ️ 提示 (可选修复)\n")
            for issue in self.result.get_infos()[:20]:  # 限制显示数量
                lines.append(f"- **[{issue.category}]** {issue.message}")
            if len(self.result.get_infos()) > 20:
                lines.append(f"- ... 还有 {len(self.result.get_infos()) - 20} 条提示")
        
        return "\n".join(lines)
    
    def generate_fix_prompt(self) -> str:
        """生成用于让大模型修复的Prompt"""
        errors = self.result.get_errors()
        warnings = self.result.get_warnings()
        
        if not errors and not warnings:
            return "当前提取结果质量良好，无需修复。"
        
        prompt_parts = []
        prompt_parts.append("# 知识图谱修复任务\n")
        prompt_parts.append("请根据以下检查结果，修复知识图谱中的问题。\n")
        
        # 原始JSON
        prompt_parts.append("## 当前提取结果\n")
        prompt_parts.append("```json")
        prompt_parts.append(json.dumps(self.kg_data.get("data", self.kg_data), ensure_ascii=False, indent=2))
        prompt_parts.append("```\n")
        
        # 需要修复的问题
        prompt_parts.append("## 需要修复的问题\n")
        
        if errors:
            prompt_parts.append("### 必须修复的错误:\n")
            for i, issue in enumerate(errors, 1):
                prompt_parts.append(f"{i}. **{issue.category}**: {issue.message}")
                if issue.entity_id:
                    prompt_parts.append(f"   - 相关实体ID: {issue.entity_id}")
                if issue.relation_index is not None:
                    prompt_parts.append(f"   - 相关关系索引: #{issue.relation_index}")
                if issue.suggestion:
                    prompt_parts.append(f"   - 修复建议: {issue.suggestion}")
                prompt_parts.append("")
        
        if warnings:
            prompt_parts.append("### 建议修复的警告:\n")
            for i, issue in enumerate(warnings, 1):
                prompt_parts.append(f"{i}. **{issue.category}**: {issue.message}")
                if issue.suggestion:
                    prompt_parts.append(f"   - 修复建议: {issue.suggestion}")
                prompt_parts.append("")
        
        # 修复要求
        prompt_parts.append("## 修复要求\n")
        prompt_parts.append("1. 修复所有ERROR级别的问题")
        prompt_parts.append("2. 尽量修复WARNING级别的问题")
        prompt_parts.append("3. 保持已正确的实体和关系不变")
        prompt_parts.append("4. 确保输出格式与原始JSON结构一致")
        prompt_parts.append("5. 仅输出修复后的JSON，不要添加解释\n")
        
        # 原文（如果有）
        if self.markdown:
            prompt_parts.append("## 原始文献内容（供参考）\n")
            prompt_parts.append("```markdown")
            # 截取前8000字符
            prompt_parts.append(self.markdown[:8000])
            if len(self.markdown) > 8000:
                prompt_parts.append("\n... (内容已截断)")
            prompt_parts.append("```\n")
        
        prompt_parts.append("## 输出格式\n")
        prompt_parts.append("请输出修复后的完整JSON：")
        prompt_parts.append('{"entities":[...], "relations":[...]}')
        
        return "\n".join(prompt_parts)


# ==================== 主函数 ====================

def check_and_report(json_path: str, markdown_path: str = None, output_dir: str = ".") -> Dict:
    """
    检查知识图谱提取结果并生成报告
    
    Args:
        json_path: 提取结果JSON文件路径
        markdown_path: 原始文献markdown文件路径（可选）
        output_dir: 输出目录
    
    Returns:
        包含检查结果的字典
    """
    # 加载数据
    with open(json_path, 'r', encoding='utf-8') as f:
        kg_data = json.load(f)
    
    markdown_content = None
    if markdown_path:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
    
    # 运行检查
    checker = KnowledgeGraphChecker(kg_data, markdown_content)
    result = checker.run_all_checks()
    
    # 生成报告
    reporter = ReportGenerator(result, kg_data, markdown_content)
    
    summary_report = reporter.generate_summary_report()
    fix_prompt = reporter.generate_fix_prompt()
    
    # 保存报告
    import os
    summary_path = os.path.join(output_dir, "check_report.md")
    prompt_path = os.path.join(output_dir, "fix_prompt.md")
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_report)
    
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(fix_prompt)
    
    print(f"检查完成！")
    print(f"- 摘要报告: {summary_path}")
    print(f"- 修复Prompt: {prompt_path}")
    print(f"\n统计:")
    print(f"  错误: {result.stats.get('error_count', 0)}")
    print(f"  警告: {result.stats.get('warning_count', 0)}")
    print(f"  提示: {result.stats.get('info_count', 0)}")
    
    return {
        "result": result,
        "summary_report": summary_report,
        "fix_prompt": fix_prompt,
        "stats": result.stats
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python kg_checker.py <json_path> [markdown_path] [output_dir]")
        print("示例: python kg_checker.py extracted.json original.md ./output")
        sys.exit(1)
    
    json_path = sys.argv[1]
    markdown_path = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "."
    
    check_and_report(json_path, markdown_path, output_dir)
