"""
基于知识图谱的多轮对话问答系统 - 完整优化版 V2

核心优化：
1. 别名解析：自动识别缩写与全称的对应关系（PHQ ↔ polyhydroquinone）
2. 多跳属性检索：Material -> Property -> Value -> Condition 完整链条
3. 合成路径检索：追踪 SYNTHESIZED_FROM 关系
4. 表征方法检索：追踪 CHARACTERIZED_BY 关系
5. 反应机理检索：追踪 Reaction/Mechanism 相关关系
6. 影响关系检索：追踪 IMPROVES/REDUCES 关系
7. 官能团检索：追踪 HAS_FUNCTIONAL_GROUP 关系
8. 智能问题分类：根据问题关键词选择最佳检索策略

核心流程：问题解析 → 别名扩展 → 多策略图检索 → 推理整合 → 答案生成 → 上下文记忆
"""

import os
import sys
import json
import re
import time
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from neo4j import GraphDatabase, basic_auth
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加同目录到sys.path，支持导入同目录的其他模块
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# 全局标志：openai 是否可用
_openai_available = False
_openai_import_error = None

try:
    from openai import OpenAI
    _openai_available = True
except ImportError as e:
    _openai_import_error = str(e)
    print(f"⚠️  警告：无法导入 openai 库 - {e}")


class KimiEntityRelationExtractor:
    """使用Kimi模型进行实体和关系提取"""
    
    def __init__(self, api_key: str = None, model: str = "kimi-k2.6"):
        global _openai_available

        if api_key is None:
            api_key = __import__("os").environ.get("MOONSHOT_API_KEY", "")
        
        if not api_key:
            print("⚠️  错误：API 密钥为空")
            self.client = None
            return
        
        # 检查 openai 是否可用
        if not _openai_available:
            print(f"❌ 错误：无法使用 openai 库 - {_openai_import_error}")
            self.client = None
            return
        
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1",
            )
        except Exception as e:
            print(f"❌ 错误：初始化 OpenAI 客户端失败 - {e}")
            self.client = None
        
        self.model = model
        if self.client:
            print(f"✅ Kimi 提取器初始化完成 - 使用模型: {self.model}")
    
    def _create_extraction_prompt(self, text: str) -> str:
        prompt = f"""你是液流电池领域的知识图谱实体关系提取专家。请从用户问题中提取实体和关系。

【实体类型】
- Material: 材料、化合物（如PHQ、polyhydroquinone、PI1等）
- Species: 离子、自由基（如H+、e-等）
- Property: 性能指标（如溶解度、效率、容量等）
- Value: 数值+单位
- Condition: 实验条件（如温度、浓度等）
- Reaction: 化学/电化学反应
- Mechanism: 反应机理
- Component: 电池组件（如正极液、负极液等）
- Method: 表征/合成方法
- Device: 电池/设备
- FunctionalGroup: 官能团

【重要】请识别用户问题的查询意图类型：
- property_value: 询问属性值（如"溶解度是多少"、"效率多少"）
- synthesis: 询问合成/制备（如"怎么合成"、"由什么制备"）
- characterization: 询问表征方法（如"用什么方法表征"、"怎么测试"）
- reaction: 询问反应过程（如"反应过程"、"氧化还原"）
- mechanism: 询问机理（如"机理"、"原理"）
- structure: 询问结构/官能团（如"有什么官能团"、"结构"）
- usage: 询问用途（如"用作什么"、"用途"）
- comparison: 询问比较/配对（如"和什么配对"、"比较"）
- effect: 询问影响（如"什么能提高"、"影响因素"）
- general: 一般性查询

【输出格式】JSON格式：
{{
  "entities": [
    {{"id": 1, "name": "实体名", "type": "类型", "aliases": ["可能的别名/缩写"]}}
  ],
  "relations": [
    {{"e1_name": "实体1", "relation": "关系", "e2_name": "实体2"}}
  ],
  "query_intent": "查询意图类型",
  "target_properties": ["用户想了解的具体属性，如溶解度、效率等"]
}}

待提取用户问题：
{text}
"""
        return prompt
    
    def extract(self, text: str, timeout: int = 60) -> Dict:
        if not hasattr(self, 'client') or not self.client:
            return {"entities": [], "relations": [], "query_intent": "general"}
        
        try:
            prompt = self._create_extraction_prompt(text)
            
            _t = 1.0 if isinstance(self.model, str) and self.model.startswith("kimi-k2.") else 0.3
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=_t,
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            extracted_data = json.loads(content.strip())
            print(f"✅ 提取成功: {len(extracted_data.get('entities', []))} 个实体, 意图: {extracted_data.get('query_intent', 'general')}")
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ 提取失败: {str(e)}")
            return {"entities": [], "relations": [], "query_intent": "general"}


class QuestionAnalyzer:
    """问题解析器 - 增强版"""
    
    def __init__(self, kimi_api_key: str = None):
        self.kimi_extractor = KimiEntityRelationExtractor(api_key=kimi_api_key)
        
        # 查询意图关键词映射
        self.intent_keywords = {
            'property_value': ['溶解度', '黏度', '电位', '容量', '效率', '数值', '多少', '是多少', 
                              'solubility', 'viscosity', 'potential', 'capacity', 'efficiency'],
            'synthesis': ['合成', '制备', '由什么', '怎么做', '原料', 'synthesize', 'prepare', 'from'],
            'characterization': ['表征', '测试', '测量', '检测', '分析', 'characterize', 'test', 'measure'],
            'reaction': ['反应', '过程', '氧化', '还原', 'redox', 'reaction', '电化学'],
            'mechanism': ['机理', '原理', '机制', 'mechanism', 'principle'],
            'structure': ['结构', '官能团', '基团', 'structure', 'functional group', 'group'],
            'usage': ['用途', '用作', '应用', '作为', 'use', 'application', 'as'],
            'comparison': ['比较', '对比', '配对', '和什么', 'compare', 'pair', 'vs'],
            'effect': ['影响', '提高', '降低', '改善', '因素', 'improve', 'reduce', 'effect', 'factor']
        }
    
    def analyze(self, question: str) -> Dict:
        kimi_result = self.kimi_extractor.extract(question)
        
        entities = [e.get('name') for e in kimi_result.get('entities', [])]
        
        # 收集所有可能的搜索关键词（包括别名）
        search_keywords = set()
        for e in kimi_result.get('entities', []):
            search_keywords.add(e.get('name', ''))
            for alias in e.get('aliases', []):
                search_keywords.add(alias)
        
        # 确定查询意图
        query_intent = kimi_result.get('query_intent', self._detect_intent_by_keywords(question))
        target_properties = kimi_result.get('target_properties', [])
        
        analysis = {
            'original': question,
            'query_intent': query_intent,
            'entities': entities,
            'search_keywords': list(search_keywords),
            'target_properties': target_properties,
            'relations': kimi_result.get('relations', []),
            'kimi_result': kimi_result
        }
        
        return analysis
    
    def _detect_intent_by_keywords(self, question: str) -> str:
        """基于关键词检测查询意图"""
        question_lower = question.lower()
        
        for intent, keywords in self.intent_keywords.items():
            if any(kw in question_lower for kw in keywords):
                return intent
        
        return 'general'


class GraphReasoningEngine:
    """图推理引擎 - 完整优化版"""
    
    def __init__(self, driver):
        self.driver = driver
        self._alias_cache = {}  # 别名缓存
        self._build_alias_cache()
    
    def _build_alias_cache(self):
        """构建别名缓存 - 基于DERIVED_FROM关系"""
        if not self.driver:
            return
        
        try:
            with self.driver.session() as session:
                # 查找所有 DERIVED_FROM 关系（缩写 -> 全称）
                query = """
                MATCH (abbr)-[r:DERIVED_FROM]->(full)
                RETURN abbr.name as abbreviation, full.name as full_name
                """
                result = session.run(query)
                
                for record in result:
                    abbr = record['abbreviation']
                    full = record['full_name']
                    # 双向映射
                    self._alias_cache[abbr.lower()] = full
                    self._alias_cache[full.lower()] = abbr
                
                print(f"✅ 别名缓存已构建: {len(self._alias_cache)//2} 对别名")
        except Exception as e:
            print(f"⚠️  构建别名缓存失败: {str(e)}")
    
    def expand_with_aliases(self, entity_name: str) -> List[str]:
        """扩展实体名称，包含其别名/全称"""
        names = [entity_name]
        
        # 从缓存查找别名
        key = entity_name.lower()
        if key in self._alias_cache:
            names.append(self._alias_cache[key])
        
        # 动态查询数据库中的别名关系
        if self.driver:
            try:
                with self.driver.session() as session:
                    query = """
                    MATCH (a)-[:DERIVED_FROM]-(b)
                    WHERE toLower(a.name) = toLower($name) OR toLower(b.name) = toLower($name)
                    RETURN DISTINCT a.name as name1, b.name as name2
                    """
                    result = session.run(query, name=entity_name)
                    for record in result:
                        if record['name1'] not in names:
                            names.append(record['name1'])
                        if record['name2'] not in names:
                            names.append(record['name2'])
            except:
                pass
        
        return names
    
    def search_entity_flexible(self, entity_name: str) -> List[Dict]:
        """灵活的实体搜索 - 支持别名、属性搜索"""
        if not self.driver:
            return []
        
        # 首先扩展别名
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        seen_names = set()
        
        try:
            with self.driver.session() as session:
                for name in search_names:
                    # 1. 精确匹配
                    query1 = """
                    MATCH (n) WHERE toLower(n.name) = toLower($name)
                    RETURN n.name as name, labels(n)[0] as type, properties(n) as properties
                    """
                    for record in session.run(query1, name=name):
                        if record['name'] not in seen_names:
                            seen_names.add(record['name'])
                            results.append(dict(record))
                    
                    # 2. 包含匹配
                    query2 = """
                    MATCH (n) WHERE toLower(n.name) CONTAINS toLower($name)
                    RETURN n.name as name, labels(n)[0] as type, properties(n) as properties
                    LIMIT 20
                    """
                    for record in session.run(query2, name=name):
                        if record['name'] not in seen_names:
                            seen_names.add(record['name'])
                            results.append(dict(record))
                
                # 3. 属性值搜索（搜索equation等）
                query3 = """
                MATCH (n)
                WHERE any(key in keys(n) WHERE toString(n[key]) CONTAINS $name)
                RETURN n.name as name, labels(n)[0] as type, properties(n) as properties
                LIMIT 10
                """
                try:
                    for record in session.run(query3, name=entity_name):
                        if record['name'] not in seen_names:
                            seen_names.add(record['name'])
                            results.append(dict(record))
                except:
                    pass
                
        except Exception as e:
            print(f"   搜索失败: {str(e)}")
        
        return results
    
    def get_property_values(self, entity_name: str) -> List[Dict]:
        """获取实体的属性-值链条 (Material -> Property -> Value -> Condition)"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (m)-[:HAS_PROPERTY]->(p)-[:HAS_VALUE]->(v)
                    WHERE toLower(m.name) CONTAINS toLower($name) OR toLower(m.name) = toLower($name)
                    OPTIONAL MATCH (p)-[:MEASURED_AT]->(c)
                    RETURN m.name as material, p.name as property, v.name as value, 
                           c.name as condition, properties(p) as prop_details
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   属性值查询失败: {str(e)}")
        
        return results
    
    def get_synthesis_info(self, entity_name: str) -> List[Dict]:
        """获取合成信息 (SYNTHESIZED_FROM关系)"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (product)-[:SYNTHESIZED_FROM]->(reactant)
                    WHERE toLower(product.name) CONTAINS toLower($name) OR toLower(product.name) = toLower($name)
                    RETURN product.name as product, collect(reactant.name) as reactants,
                           labels(product)[0] as product_type
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   合成信息查询失败: {str(e)}")
        
        return results
    
    def get_characterization_methods(self, entity_name: str) -> List[Dict]:
        """获取表征方法 (CHARACTERIZED_BY关系)"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (material)-[:CHARACTERIZED_BY]->(method)
                    WHERE toLower(material.name) CONTAINS toLower($name) OR toLower(material.name) = toLower($name)
                    RETURN material.name as material, collect(method.name) as methods,
                           labels(material)[0] as material_type
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   表征方法查询失败: {str(e)}")
        
        return results
    
    def get_reaction_info(self, entity_name: str) -> List[Dict]:
        """获取反应信息（全面）"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    # 1. 从物质找相关反应
                    query1 = """
                    MATCH (r:Reaction)-[rel]-(m)
                    WHERE toLower(m.name) CONTAINS toLower($name) OR toLower(m.name) = toLower($name)
                    RETURN r.name as reaction_name, r.equation as equation,
                           type(rel) as relation_type, m.name as related_entity,
                           labels(m)[0] as entity_type, properties(r) as reaction_props
                    """
                    for record in session.run(query1, name=name):
                        results.append(dict(record))
                    
                    # 2. 直接搜索反应名
                    query2 = """
                    MATCH (r:Reaction)
                    WHERE toLower(r.name) CONTAINS toLower($name)
                    OPTIONAL MATCH (r)-[rel]-(related)
                    RETURN r.name as reaction_name, r.equation as equation,
                           collect({relation: type(rel), entity: related.name, type: labels(related)[0]}) as related_entities,
                           properties(r) as reaction_props
                    """
                    for record in session.run(query2, name=name):
                        if record['reaction_name']:
                            results.append(dict(record))
        except Exception as e:
            print(f"   反应信息查询失败: {str(e)}")
        
        return results
    
    def get_mechanism_info(self, entity_name: str) -> List[Dict]:
        """获取机理信息"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (mech:Mechanism)-[rel]-(related)
                    WHERE toLower(mech.name) CONTAINS toLower($name) 
                       OR toLower(related.name) CONTAINS toLower($name)
                    RETURN mech.name as mechanism_name, properties(mech) as mechanism_props,
                           type(rel) as relation, related.name as related_entity,
                           labels(related)[0] as related_type
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   机理信息查询失败: {str(e)}")
        
        return results
    
    def get_functional_groups(self, entity_name: str) -> List[Dict]:
        """获取官能团信息"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (m)-[:HAS_FUNCTIONAL_GROUP]->(fg)
                    WHERE toLower(m.name) CONTAINS toLower($name) OR toLower(m.name) = toLower($name)
                    RETURN m.name as material, collect(fg.name) as functional_groups
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   官能团查询失败: {str(e)}")
        
        return results
    
    def get_usage_info(self, entity_name: str) -> List[Dict]:
        """获取用途信息 (USED_AS关系)"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (m)-[:USED_AS]->(c)
                    WHERE toLower(m.name) CONTAINS toLower($name) OR toLower(m.name) = toLower($name)
                    RETURN m.name as material, collect(c.name) as usages
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   用途查询失败: {str(e)}")
        
        return results
    
    def get_pairing_info(self, entity_name: str) -> List[Dict]:
        """获取配对信息 (PAIRED_WITH关系)"""
        if not self.driver:
            return []
        
        search_names = self.expand_with_aliases(entity_name)
        
        results = []
        try:
            with self.driver.session() as session:
                for name in search_names:
                    query = """
                    MATCH (m1)-[:PAIRED_WITH]-(m2)
                    WHERE toLower(m1.name) CONTAINS toLower($name) OR toLower(m1.name) = toLower($name)
                    RETURN m1.name as material, collect(DISTINCT m2.name) as paired_with
                    """
                    for record in session.run(query, name=name):
                        results.append(dict(record))
        except Exception as e:
            print(f"   配对信息查询失败: {str(e)}")
        
        return results
    
    def get_effect_info(self, entity_name: str = None) -> List[Dict]:
        """获取影响关系 (IMPROVES/REDUCES)"""
        if not self.driver:
            return []
        
        results = []
        try:
            with self.driver.session() as session:
                if entity_name:
                    search_names = self.expand_with_aliases(entity_name)
                    for name in search_names:
                        query = """
                        MATCH (a)-[r:IMPROVES|REDUCES]->(b)
                        WHERE toLower(a.name) CONTAINS toLower($name) 
                           OR toLower(b.name) CONTAINS toLower($name)
                        RETURN a.name as factor, type(r) as effect_type, b.name as property
                        """
                        for record in session.run(query, name=name):
                            results.append(dict(record))
                else:
                    # 获取所有影响关系
                    query = """
                    MATCH (a)-[r:IMPROVES|REDUCES]->(b)
                    RETURN a.name as factor, type(r) as effect_type, b.name as property
                    """
                    for record in session.run(query):
                        results.append(dict(record))
        except Exception as e:
            print(f"   影响关系查询失败: {str(e)}")
        
        return results
    
    def get_all_relations(self, entity_name: str, depth: int = 2) -> Dict:
        """获取实体的所有关系（完整版）"""
        if not self.driver:
            return {}
        
        search_names = self.expand_with_aliases(entity_name)
        
        all_relations = {
            'outgoing': [],
            'incoming': [],
            'entity_info': None
        }
        
        try:
            with self.driver.session() as session:
                for name in search_names:
                    # 获取实体本身的信息
                    query_self = """
                    MATCH (n)
                    WHERE toLower(n.name) = toLower($name) OR toLower(n.name) CONTAINS toLower($name)
                    RETURN n.name as name, labels(n)[0] as type, properties(n) as props
                    LIMIT 1
                    """
                    result = session.run(query_self, name=name).single()
                    if result and not all_relations['entity_info']:
                        all_relations['entity_info'] = dict(result)
                    
                    # 出边关系
                    query_out = """
                    MATCH (a)-[r]->(b)
                    WHERE toLower(a.name) = toLower($name) OR toLower(a.name) CONTAINS toLower($name)
                    RETURN a.name as source, type(r) as relation, b.name as target,
                           labels(b)[0] as target_type, properties(b) as target_props
                    LIMIT 50
                    """
                    for record in session.run(query_out, name=name):
                        all_relations['outgoing'].append(dict(record))
                    
                    # 入边关系
                    query_in = """
                    MATCH (a)-[r]->(b)
                    WHERE toLower(b.name) = toLower($name) OR toLower(b.name) CONTAINS toLower($name)
                    RETURN a.name as source, type(r) as relation, b.name as target,
                           labels(a)[0] as source_type, properties(a) as source_props
                    LIMIT 50
                    """
                    for record in session.run(query_in, name=name):
                        all_relations['incoming'].append(dict(record))
                        
        except Exception as e:
            print(f"   完整关系查询失败: {str(e)}")
        
        return all_relations
    
    def find_entity_paths(self, source: str, target: str, max_length: int = 4) -> List[Dict]:
        """查找两个实体之间的路径"""
        if not self.driver:
            return []
        
        source_names = self.expand_with_aliases(source)
        target_names = self.expand_with_aliases(target)
        
        results = []
        try:
            with self.driver.session() as session:
                for s in source_names:
                    for t in target_names:
                        query = f"""
                        MATCH path = (a)-[*1..{max_length}]-(b)
                        WHERE (toLower(a.name) CONTAINS toLower($source) OR toLower(a.name) = toLower($source))
                          AND (toLower(b.name) CONTAINS toLower($target) OR toLower(b.name) = toLower($target))
                        WITH path, length(path) as len,
                             [node in nodes(path) | node.name] as nodes,
                             [rel in relationships(path) | type(rel)] as relations
                        RETURN nodes, relations, len
                        ORDER BY len
                        LIMIT 5
                        """
                        for record in session.run(query, source=s, target=t):
                            results.append(dict(record))
        except Exception as e:
            print(f"   路径查询失败: {str(e)}")
        
        return results


class ContextMemory:
    """上下文记忆管理器"""
    
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.conversation_history = []
        self.discovered_entities: Set[str] = set()
        self.entity_relationships: Dict[str, Set[str]] = defaultdict(set)
    
    def add_turn(self, role: str, content: str, context: Dict = None):
        self.conversation_history.append({
            'role': role,
            'content': content,
            'context': context or {}
        })
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
    
    def update_discovered_entities(self, entities: List[str]):
        self.discovered_entities.update(entities)
    
    def add_entity_relation(self, entity1: str, entity2: str):
        self.entity_relationships[entity1].add(entity2)
        self.entity_relationships[entity2].add(entity1)
    
    def get_context_entities(self) -> List[str]:
        return sorted(
            list(self.discovered_entities),
            key=lambda e: len(self.entity_relationships.get(e, set())),
            reverse=True
        )[:5]


class GraphQA:
    """完整的图谱问答系统 - V2"""
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = __import__("os").environ.get("NEO4J_PASSWORD", ""),
                 kimi_api_key: str = None):
        
        # 从同目录加载配置
        self._load_local_config()
        
        self.question_analyzer = QuestionAnalyzer(kimi_api_key=kimi_api_key)
        self.reasoning_engine = None
        self.context_memory = ContextMemory()
        
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        
        if self._connect_to_neo4j():
            self.reasoning_engine = GraphReasoningEngine(self.driver)
    
    def _load_local_config(self):
        """从同目录加载配置文件"""
        try:
            # 尝试加载 path.py 配置
            from pathlib import Path
            current_dir = Path(__file__).parent
            
            # 检查是否存基于 path.py 配置文件
            path_config_file = current_dir / "path.py"
            if path_config_file.exists():
                with open(path_config_file, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                print(f"  ✅ 已从同目录加载配置: {path_config_file}")
            
            # 检查是否存基于 knowledge_graph.json
            kg_file = current_dir / "knowledge_graph.json"
            if kg_file.exists():
                file_size_mb = kg_file.stat().st_size / (1024 * 1024)
                print(f"  ✅ 找到知识图谱文件: {kg_file.name} ({file_size_mb:.2f} MB)")
        except Exception as e:
            print(f"  ⚠️  加载本地配置失败: {str(e)}")
    
    def _connect_to_neo4j(self) -> bool:
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=basic_auth(self.neo4j_user, self.neo4j_password),
                encrypted=False
            )
            with self.driver.session() as session:
                session.run("RETURN 1").consume()
            print("✅ 成功连接到Neo4j数据库")
            return True
        except Exception as e:
            print(f"❌ 无法连接到Neo4j数据库: {str(e)}")
            return False
    
    def query(self, question: str) -> Dict:
        """完整的图谱问答流程，返回答案和文献来源"""
        print(f"\n[1/5] 开始问题解析...")
        
        # 1. 问题解析
        analysis = self.question_analyzer.analyze(question)
        query_intent = analysis.get('query_intent', 'general')
        entities = analysis.get('entities', [])
        
        print(f"      查询意图: {query_intent}")
        print(f"      提取实体: {entities}")
        if analysis.get('target_properties'):
            print(f"      目标属性: {analysis['target_properties']}")
        
        # 2. 基于意图的智能检索
        print(f"\n[2/5] 开始智能图检索 (策略: {query_intent})...")
        search_results = self._intelligent_search(analysis)
        
        # 3. 推理整合
        print(f"\n[3/5] 开始推理整合...")
        reasoning_result = self._reasoning_and_aggregation(analysis, search_results)
        
        # 4. 答案生成
        print(f"\n[4/5] 开始答案生成...")
        answer, sources, entity_source_map = self._generate_answer(analysis, reasoning_result, search_results)
        
        # 5. 上下文记忆
        print(f"\n[5/5] 更新上下文记忆...")
        self._update_context_memory(analysis, search_results)
        
        return {
            'answer': answer,
            'sources': sources,
            'entity_source_map': entity_source_map,
            'search_results': search_results  # 返回原始搜索结果（Neo4j数据）
        }
    
    def get_raw_search_results(self, question: str, analysis: Dict = None) -> Dict:
        """获取原始的图谱搜索结果（仅返回Neo4j数据库中的实体和关系，不生成答案）
        
        返回格式:
        {
            'entities': [...],  # 从Neo4j搜索到的实体列表
            'relations': [...],  # 从Neo4j搜索到的关系列表
            'property_values': [...],  # 属性-值信息
            'reaction_info': [...],  # 反应信息
            'synthesis_info': [...],  # 合成信息
            ...
        }
        """
        if not self.reasoning_engine:
            return {}
        
        # 解析问题
        if analysis is None:
            analysis = self.question_analyzer.analyze(question)
        
        # 执行智能检索（返回所有Neo4j数据）
        search_results = self._intelligent_search(analysis)
        
        return search_results

    def get_raw_search_results_from_entities(self, question: str, entities: List[str], query_intent: str) -> Dict:
        """Reuse the production parsing stage instead of issuing a second LLM extraction."""
        names = list(dict.fromkeys(str(name).strip() for name in entities if str(name).strip()))
        return self.get_raw_search_results(question, analysis={
            'original': question, 'entities': names, 'search_keywords': names,
            'query_intent': query_intent or 'general', 'target_properties': [], 'relations': [],
        })
    
    def _intelligent_search(self, analysis: Dict) -> Dict:
        """基于查询意图的智能检索（极速优化版）
        
        优化策略：
        1. 【实体截断】只取最相似的 Top 3-5 个实体进行扩展
        2. 【关系截断】每个实体最多只查 10-20 条最重要的边
        3. 【砍掉Path】问答场景下，多跳路径（A->B->C）是噪音，成本指数级
        4. 【关键词精化】只取 top 3 关键词，避免重复计算
        
        预期效果：性能提升 70-80%（从3-5s降至0.5-1s）
        """
        if not self.reasoning_engine:
            return {}
        
        results = {
            'entities': [],
            'property_values': [],
            'synthesis_info': [],
            'characterization_methods': [],
            'reaction_info': [],
            'mechanism_info': [],
            'functional_groups': [],
            'usage_info': [],
            'pairing_info': [],
            'effect_info': [],
            'all_relations': [],
            'paths': []  # 【移除】不再使用路径检索
        }
        
        entities = analysis.get('entities', [])
        search_keywords = analysis.get('search_keywords', entities)
        query_intent = analysis.get('query_intent', 'general')
        
        if not entities and not search_keywords:
            return results
        
        # 【优化】关键词精化：只取 top 3，避免冗余计算
        all_keywords = list(dict.fromkeys(entities + search_keywords))[:3]
        
        # 【优化】阶段 1: 基础实体搜索 - 只取 Top 3-5 个最相似的实体
        search_start = time.time()
        temp_entities = []
        for kw in all_keywords:
            found = self.reasoning_engine.search_entity_flexible(kw)
            temp_entities.extend(found)
        
        # 去重并限制在 Top 5
        seen = set()
        for entity in temp_entities:
            if isinstance(entity, dict):
                entity_name = entity.get('name', '')
                if entity_name and entity_name not in seen:
                    results['entities'].append(entity)
                    seen.add(entity_name)
                    if len(results['entities']) >= 5:  # 【截断】仅保留Top 5
                        break
            elif isinstance(entity, str) and entity not in seen:
                results['entities'].append(entity)
                seen.add(entity)
                if len(results['entities']) >= 5:
                    break
        
        entity_search_time = time.time() - search_start
        print(f"      ✓ 实体搜索: 找到 {len(results['entities'])} 个匹配 ({entity_search_time:.3f}s) ")
        
        # 【优化】阶段 2: 意图相关检索 - 只处理 Top 3 关键词
        primary_entity = entities[0] if entities else (search_keywords[0] if search_keywords else '')
        
        intent_start = time.time()
        # 只遍历 top 3 关键词（已在上面限制）
        if query_intent == 'property_value' or query_intent == 'general':
            for kw in all_keywords:
                pv = self.reasoning_engine.get_property_values(kw)
                results['property_values'].extend(pv)
        
        if query_intent == 'synthesis' or query_intent == 'general':
            for kw in all_keywords:
                syn = self.reasoning_engine.get_synthesis_info(kw)
                results['synthesis_info'].extend(syn)
        
        if query_intent == 'characterization' or query_intent == 'general':
            for kw in all_keywords:
                char = self.reasoning_engine.get_characterization_methods(kw)
                results['characterization_methods'].extend(char)
        
        if query_intent == 'reaction' or query_intent == 'general':
            for kw in all_keywords:
                rxn = self.reasoning_engine.get_reaction_info(kw)
                results['reaction_info'].extend(rxn)
        
        if query_intent == 'mechanism' or query_intent == 'general':
            for kw in all_keywords:
                mech = self.reasoning_engine.get_mechanism_info(kw)
                results['mechanism_info'].extend(mech)
        
        if query_intent == 'structure' or query_intent == 'general':
            for kw in all_keywords:
                fg = self.reasoning_engine.get_functional_groups(kw)
                results['functional_groups'].extend(fg)
        
        if query_intent == 'usage' or query_intent == 'general':
            for kw in all_keywords:
                usage = self.reasoning_engine.get_usage_info(kw)
                results['usage_info'].extend(usage)
        
        if query_intent == 'comparison' or query_intent == 'general':
            for kw in all_keywords:
                pair = self.reasoning_engine.get_pairing_info(kw)
                results['pairing_info'].extend(pair)
        
        if query_intent == 'effect':
            for kw in all_keywords:
                eff = self.reasoning_engine.get_effect_info(kw)
                results['effect_info'].extend(eff)
            if not results['effect_info']:
                results['effect_info'] = self.reasoning_engine.get_effect_info(None)
        
        intent_time = time.time() - intent_start
        print(f"      ✓ 意图检索: 属性{len(results['property_values'])} 合成{len(results['synthesis_info'])} 反应{len(results['reaction_info'])} ({intent_time:.3f}s)")
        
        # 【优化】阶段 3: 关系挖掘 - 仅处理 Primary Entity 的边，限制最多 15 条
        parallel_start = time.time()
        parallel_results = {}
        
        # 仅获取 primary_entity 的关系（取消Path检索）
        if primary_entity:
            try:
                all_rels = self.reasoning_engine.get_all_relations(primary_entity)
                if all_rels:
                    # 【截断】限制出边和入边各 10 条
                    truncated_rels = {
                        'entity_info': all_rels.get('entity_info'),
                        'outgoing': all_rels.get('outgoing', [])[:10],  # 仅保留Top 10
                        'incoming': all_rels.get('incoming', [])[:10]   # 仅保留Top 10
                    }
                    results['all_relations'].append(truncated_rels)
                    out_count = len(truncated_rels.get('outgoing', []))
                    in_count = len(truncated_rels.get('incoming', []))
                    print(f"      ✓ 关系检索: 出边 {out_count} 条, 入边 {in_count} 条 ")
            except Exception as e:
                print(f"      ⚠️  关系检索失败: {str(e)}")
        
        # 【移除】不再执行路径检索（多跳路径在问答场景是噪音，成本指数级）
        # 【说明】多跳路径（A->B->C）对于问答场景意义不大，且计算复杂度高
        
        parallel_time = time.time() - parallel_start
        print(f"      ⚡ 关系检索耗时: {parallel_time:.3f}s")
        
        return results
    
    def _safe_get_effect_info(self, all_keywords: List[str]) -> List[Dict]:
        """安全的影响关系获取（用于并行执行）"""
        if not self.reasoning_engine:
            return []
        
        results = []
        for kw in all_keywords[:3]:
            try:
                eff = self.reasoning_engine.get_effect_info(kw)
                results.extend(eff)
            except:
                pass
        
        # 如果没有找到特定实体的影响关系，获取所有
        if not results:
            try:
                results = self.reasoning_engine.get_effect_info(None)
            except:
                pass
        
        return results
    
    def _reasoning_and_aggregation(self, analysis: Dict, search_results: Dict) -> Dict:
        """推理整合"""
        reasoning_result = {
            'primary_entity': None,
            'confidence': 0.0,
            'info_summary': {}
        }
        
        entities = analysis.get('entities', [])
        if entities:
            reasoning_result['primary_entity'] = entities[0]
        
        # 计算置信度
        total_results = 0
        for key, value in search_results.items():
            if isinstance(value, list):
                total_results += len(value)
        
        reasoning_result['confidence'] = min(0.95, total_results * 0.05)
        
        # 生成信息摘要
        if search_results.get('property_values'):
            reasoning_result['info_summary']['properties'] = len(search_results['property_values'])
        if search_results.get('reaction_info'):
            reasoning_result['info_summary']['reactions'] = len(search_results['reaction_info'])
        if search_results.get('synthesis_info'):
            reasoning_result['info_summary']['synthesis'] = len(search_results['synthesis_info'])
        
        print(f"      置信度: {reasoning_result['confidence']:.2f}")
        print(f"      信息摘要: {reasoning_result['info_summary']}")
        
        return reasoning_result
    
    def _generate_answer(self, analysis: Dict, reasoning_result: Dict, search_results: Dict) -> Tuple[str, List[str], Dict]:
        """答案生成，返回答案、文献来源列表和来源映射"""
        original_question = analysis.get('original', '')
        retrieved_info, sources, entity_source_map = self._format_retrieved_info(search_results, analysis)
        
        answer = self._ask_kimi_for_answer(original_question, retrieved_info, analysis.get('query_intent', 'general'))
        print(f"      已生成答案")
        
        # 在答案末尾添加文献来源和来源映射
        if sources or entity_source_map:
            answer_with_sources = self._append_sources_and_mapping(answer, sources, entity_source_map)
            return answer_with_sources, sources, entity_source_map
        
        return answer, sources, entity_source_map
    
    def _format_retrieved_info(self, search_results: Dict, analysis: Dict) -> Tuple[str, List[str], Dict]:
        """格式化检索到的信息，同时收集文献来源"""
        info_parts = []
        sources_set = set()  # 使用set去重
        entity_source_map = {}  # 实体->来源映射
        
        query_intent = analysis.get('query_intent', 'general')
        info_parts.append(f"【查询意图】{query_intent}")
        info_parts.append(f"【提取实体】{', '.join(analysis.get('entities', []))}")
        
        # 1. 属性值信息
        pv = search_results.get('property_values', [])
        if pv:
            info_parts.append("\n【🔢 属性-数值信息】")
            for item in pv:
                material = item.get('material', '')
                prop = item.get('property', '')
                value = item.get('value', '')
                condition = item.get('condition', '')
                line = f"  • {material} 的 {prop} = {value}"
                if condition:
                    line += f" (条件: {condition})"
                info_parts.append(line)
        
        # 2. 反应信息
        rxn = search_results.get('reaction_info', [])
        if rxn:
            info_parts.append("\n【⚗️ 反应信息】")
            seen_reactions = set()
            for item in rxn:
                rxn_name = item.get('reaction_name', '')
                if rxn_name and rxn_name not in seen_reactions:
                    seen_reactions.add(rxn_name)
                    equation = item.get('equation', '')
                    info_parts.append(f"  ★ {rxn_name}")
                    if equation:
                        info_parts.append(f"      方程式: {equation}")
                    # 显示相关实体
                    related = item.get('related_entities', [])
                    if related:
                        for rel in related[:5]:
                            if rel.get('entity'):
                                info_parts.append(f"      --[{rel.get('relation')}]--> {rel.get('entity')} ({rel.get('type')})")
        
        # 3. 合成信息
        syn = search_results.get('synthesis_info', [])
        if syn:
            info_parts.append("\n【🧪 合成信息】")
            for item in syn:
                product = item.get('product', '')
                reactants = item.get('reactants', [])
                info_parts.append(f"  • {product} 由以下原料合成:")
                for r in reactants:
                    info_parts.append(f"      - {r}")
        
        # 4. 表征方法
        char = search_results.get('characterization_methods', [])
        if char:
            info_parts.append("\n【🔬 表征方法】")
            for item in char:
                material = item.get('material', '')
                methods = item.get('methods', [])
                info_parts.append(f"  • {material} 的表征方法:")
                for m in methods:
                    info_parts.append(f"      - {m}")
        
        # 5. 机理信息
        mech = search_results.get('mechanism_info', [])
        if mech:
            info_parts.append("\n【⚙️ 机理信息】")
            seen_mechs = set()
            for item in mech:
                mech_name = item.get('mechanism_name', '')
                if mech_name and mech_name not in seen_mechs:
                    seen_mechs.add(mech_name)
                    info_parts.append(f"  • {mech_name}")
                    props = item.get('mechanism_props', {})
                    for k, v in props.items():
                        if k != 'name' and v:
                            info_parts.append(f"      {k}: {v}")
        
        # 6. 官能团信息
        fg = search_results.get('functional_groups', [])
        if fg:
            info_parts.append("\n【🔗 官能团信息】")
            for item in fg:
                material = item.get('material', '')
                groups = item.get('functional_groups', [])
                info_parts.append(f"  • {material} 含有官能团: {', '.join(groups)}")
        
        # 7. 用途信息
        usage = search_results.get('usage_info', [])
        if usage:
            info_parts.append("\n【📋 用途信息】")
            for item in usage:
                material = item.get('material', '')
                usages = item.get('usages', [])
                info_parts.append(f"  • {material} 用作: {', '.join(usages)}")
        
        # 8. 配对信息
        pair = search_results.get('pairing_info', [])
        if pair:
            info_parts.append("\n【🔀 配对信息】")
            for item in pair:
                material = item.get('material', '')
                paired = item.get('paired_with', [])
                info_parts.append(f"  • {material} 与以下材料配对使用: {', '.join(paired)}")
        
        # 9. 影响关系
        eff = search_results.get('effect_info', [])
        if eff:
            info_parts.append("\n【📈 影响关系】")
            for item in eff:
                factor = item.get('factor', '')
                effect_type = item.get('effect_type', '')
                prop = item.get('property', '')
                effect_word = "提高" if effect_type == "IMPROVES" else "降低"
                info_parts.append(f"  • {factor} {effect_word} {prop}")
        
        # 10. 实体基本信息 + 收集来源
        entities = search_results.get('entities', [])
        if entities:
            info_parts.append("\n【📝 实体基本信息】")
            for entity in entities[:10]:
                name = entity.get('name', '')
                etype = entity.get('type', '')
                props = entity.get('properties', {})
                info_parts.append(f"  • {name} (类型: {etype})")
                # 显示重要属性
                for k, v in props.items():
                    if k not in ['id', 'name', 'source_docs'] and v:
                        info_parts.append(f"      {k}: {v}")
                # 【重要】收集文献来源
                if 'source_docs' in props and props['source_docs']:
                    source_docs = props['source_docs']
                    if isinstance(source_docs, str):
                        sources_set.add(source_docs)
                        entity_source_map[name] = source_docs
                    elif isinstance(source_docs, list):
                        sources_set.update(source_docs)
                        entity_source_map[name] = source_docs[0] if source_docs else '未知来源'
        
        # 11. 完整关系（作为补充）
        all_rels = search_results.get('all_relations', [])
        if all_rels:
            for rel_data in all_rels[:1]:  # 只显示第一个实体的关系
                outgoing = rel_data.get('outgoing', [])
                incoming = rel_data.get('incoming', [])
                
                if outgoing:
                    info_parts.append("\n【→ 出边关系】")
                    # 按关系类型分组
                    by_rel = defaultdict(list)
                    for r in outgoing:
                        by_rel[r.get('relation', '')].append(r.get('target', ''))
                    for rel_type, targets in list(by_rel.items())[:8]:
                        info_parts.append(f"  • {rel_type}: {', '.join(targets[:5])}")
                
                if incoming:
                    info_parts.append("\n【← 入边关系】")
                    by_rel = defaultdict(list)
                    for r in incoming:
                        by_rel[r.get('relation', '')].append(r.get('source', ''))
                    for rel_type, sources in list(by_rel.items())[:8]:
                        info_parts.append(f"  • {rel_type}: {', '.join(sources[:5])}")
        
        return '\n'.join(info_parts) if info_parts else "未找到相关的图谱信息", list(sources_set), entity_source_map
    
    def _clean_source_title(self, title: str) -> str:
        """
        清理来源标题
        需求1：去除milvus前缀
        需求3：分子工具和分子查询合并为分子查询（返回None表示跳过）
        
        Args:
            title: 原始标题
            
        Returns:
            str or None: 清理后的标题，如果应该跳过则返回None
        """
        if not title:
            return title
        
        # 需求1：去除milvus前缀
        clean_title = title
        if title.startswith('milvus_'):
            clean_title = title.replace('milvus_', '', 1)
        
        # 需求3：分子工具应该跳过（只保留分子查询）
        if clean_title == '分子工具':
            return None
        
        return clean_title
    
    def _filter_and_limit_sources(self, sources: List[str], max_count: int = 2) -> List[str]:
        """
        过滤和限制文献来源数量
        需求2：最多保留两个文献标题
        需求4：如果有秘塔搜索，需要保留它
        
        Args:
            sources: 原始来源列表
            max_count: 最多保留的数量（默认2）
            
        Returns:
            List[str]: 过滤后的来源列表
        """
        processed_sources = []
        has_metaso = False  # 检查是否有秘塔搜索
        
        for source in sorted(set(sources)):
            clean_title = self._clean_source_title(source)
            if clean_title is None:  # 跳过分子工具
                continue
            
            if clean_title == '秘塔搜索':
                has_metaso = True
                continue  # 秘塔搜索暂时跳过，稍后单独处理
            
            if len(processed_sources) < max_count:
                processed_sources.append(clean_title)
        
        # 需求4：如果有秘塔搜索，加在末尾
        if has_metaso:
            processed_sources.append('秘塔搜索')
        
        return processed_sources
    
    def _append_sources_and_mapping(self, answer: str, sources: List[str], entity_source_map: Dict) -> str:
        """
        在答案末尾添加文献来源
        
        Args:
            answer: 大模型生成的答案
            sources: 文献来源列表
            entity_source_map: 实体->来源映射（暂不使用）
            
        Returns:
            str: 带有文献来源的完整答案
        """
        sections = [answer]
        
        # 只添加文献来源，不添加来源映射
        if sources:
            # 使用新的过滤函数处理来源
            processed_sources = self._filter_and_limit_sources(sources)
            
            if processed_sources:
                sources_section = "\n\n_____ 文献来源 _____\n"
                for source in processed_sources:
                    sources_section += f"✓ {source}\n"
                sections.append(sources_section.rstrip())
        
        return ''.join(sections)
    
    def _ask_kimi_for_answer(self, question: str, retrieved_info: str, query_intent: str) -> str:
        """请求Kimi生成答案"""
        try:
            # 根据查询意图调整提示词
            intent_guidance = {
                'property_value': "请重点关注【属性-数值信息】部分，给出准确的数值和测试条件。",
                'synthesis': "请重点关注【合成信息】部分，说明合成原料和方法。",
                'characterization': "请重点关注【表征方法】部分，列出所有表征手段。",
                'reaction': "请重点关注【反应信息】部分，务必给出反应方程式。",
                'mechanism': "请重点关注【机理信息】部分，解释机理原理。",
                'structure': "请重点关注【官能团信息】部分，说明结构特征。",
                'usage': "请重点关注【用途信息】部分，说明材料用途。",
                'comparison': "请重点关注【配对信息】部分，说明配对关系。",
                'effect': "请重点关注【影响关系】部分，说明各因素的影响。",
                'general': "请综合所有检索到的信息给出全面的回答。"
            }
            
            specific_guidance = intent_guidance.get(query_intent, intent_guidance['general'])
            
            answer_prompt = f"""你是一个专业的液流电池领域知识图谱问答助手。请根据从知识图谱检索到的信息回答问题。

【用户问题】
{question}

【从知识图谱检索到的完整信息】
{retrieved_info}

【回答指南】
1. {specific_guidance}
2. 优先使用检索到的具体数据和信息
3. 如果检索到了反应方程式，必须在答案中明确给出
4. 如果检索到了数值，要带上单位和测试条件
5. 如果信息不足，明确说明哪些方面的信息缺失
6. 答案要科学严谨，条理清晰
"""
            
            _mdl = self.question_analyzer.kimi_extractor.model
            _t = 1.0 if isinstance(_mdl, str) and _mdl.startswith("kimi-k2.") else 0.5
            response = self.question_analyzer.kimi_extractor.client.chat.completions.create(
                model=_mdl,
                messages=[{"role": "user", "content": answer_prompt}],
                temperature=_t,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Kimi生成答案失败: {str(e)}")
            return f"抱歉，生成答案时出错: {str(e)}"
    
    def _update_context_memory(self, analysis: Dict, search_results: Dict):
        """更新上下文记忆"""
        entities = analysis.get('entities', [])
        self.context_memory.update_discovered_entities(entities)
        
        for entity in search_results.get('entities', []):
            if entities:
                self.context_memory.add_entity_relation(entities[0], entity.get('name', ''))
        
        self.context_memory.add_turn('user', analysis.get('original', ''), {
            'query_intent': analysis.get('query_intent'),
            'entities_found': len(search_results.get('entities', []))
        })
        
        print(f"      上下文已更新")
    
    def get_graph_info(self) -> Dict:
        """获取图谱文件信息"""
        from pathlib import Path
        try:
            current_dir = Path(__file__).parent
            kg_file = current_dir / "knowledge_graph.json"
            
            if kg_file.exists():
                with open(kg_file, 'r', encoding='utf-8') as f:
                    kg_data = json.load(f)
                
                return {
                    'file_path': str(kg_file),
                    'total_nodes': len(kg_data.get('nodes', {})),
                    'total_edges': len(kg_data.get('edges', {})),
                    'is_loaded': True
                }
        except Exception as e:
            return {'error': str(e), 'is_loaded': False}
        
        return {'is_loaded': False}
    
    def display_help(self):
        """显示帮助信息"""
        help_text = """
╔════════════════════════════════════════════════════════════════╗
║     基于知识图谱的多轮对话问答系统 - 完整优化版 V2             ║
╚════════════════════════════════════════════════════════════════╝

【支持的查询类型】

1. 属性值查询 🔢
   示例: "PHQ的溶解度是多少" / "PI1的黏度"
   
2. 合成信息查询 🧪
   示例: "PHQ怎么合成的" / "PI1由什么制备"
   
3. 表征方法查询 🔬
   示例: "PHQ用什么方法表征" / "如何测试PI1"
   
4. 反应过程查询 ⚗️
   示例: "PHQ的反应过程" / "PHQ的氧化还原反应"
   
5. 机理查询 ⚙️
   示例: "电荷转移机理" / "什么机理"
   
6. 结构/官能团查询 🔗
   示例: "PHQ有什么官能团" / "PI1的结构"
   
7. 用途查询 📋
   示例: "PHQ用作什么" / "PI1的用途"
   
8. 配对关系查询 🔀
   示例: "PHQ和什么配对" / "PHQ搭配什么使用"
   
9. 影响因素查询 📈
   示例: "什么能提高效率" / "影响容量的因素"

【特殊功能】
- 自动识别别名：PHQ ↔ polyhydroquinone
- 多跳关系追踪：Material → Property → Value
- 智能意图识别：自动选择最佳检索策略

【命令】
- 'help'   : 显示帮助
- 'exit'   : 退出程序

════════════════════════════════════════════════════════════════
"""
        print(help_text)
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            print("\n✅ 数据库连接已关闭")


def _filter_and_limit_sources_helper(sources: List[str], max_count: int = 2) -> List[str]:
    """
    独立的辅助函数：过滤和限制文献来源数量
    需求2：最多保留两个文献标题
    需求4：如果有秘塔搜索，需要保留它
    
    Args:
        sources: 原始来源列表
        max_count: 最多保留的数量（默认2）
        
    Returns:
        List[str]: 过滤后的来源列表
    """
    processed_sources = []
    has_metaso = False
    
    for source in sorted(set(sources)):
        if not source:
            continue
        
        # 需求1：去除milvus前缀
        clean_title = source
        if source.startswith('milvus_'):
            clean_title = source.replace('milvus_', '', 1)
        
        # 需求3：分子工具应该跳过
        if clean_title == '分子工具':
            continue
        
        # 需求4：秘塔搜索特殊处理
        if clean_title == '秘塔搜索':
            has_metaso = True
            continue
        
        # 需求2：最多保留两个文献标题
        if len(processed_sources) < max_count:
            processed_sources.append(clean_title)
    
    # 需求4：如果有秘塔搜索，加在末尾
    if has_metaso:
        processed_sources.append('秘塔搜索')
    
    return processed_sources


def main():
    """主函数"""
    print("\n" + "="*60)
    print("欢迎使用 基于知识图谱的多轮对话问答系统 - 完整优化版 V2")
    print("="*60)
    
    print("\n📄 核心优化:")
    print("  ✓ 别名自动解析 (PHQ ↔ polyhydroquinone)")
    print("  ✓ 多跳属性检索 (Material → Property → Value)")
    print("  ✓ 智能意图识别 (9种查询类型)")
    print("  ✓ 合成/表征/反应/机理/官能团 专项检索")
    
    print("\n正在初始化问答系统...")
    qa_system = GraphQA(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password=__import__("os").environ.get("NEO4J_PASSWORD", ""),
        kimi_api_key=None
    )
    
    # 显示本地配置信息
    print("\n📁 本地配置信息:")
    graph_info = qa_system.get_graph_info()
    if graph_info.get('is_loaded'):
        print(f"  ✅ 图谱文件: {graph_info.get('file_path')}")
        print(f"  ✅ 总节点数: {graph_info.get('total_nodes')}")
        print(f"  ✅ 总边数: {graph_info.get('total_edges')}")
    
    if not qa_system.driver:
        print("\n❌ 无法连接到Neo4j数据库")
        return
    
    print("\n💡 输入 'help' 查看帮助信息")
    print("   输入 'exit' 退出程序\n")
    
    try:
        while True:
            try:
                user_input = input("\n👤 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'help':
                    qa_system.display_help()
                    continue
                elif user_input.lower() == 'exit':
                    print("\n👋 感谢使用，再见！")
                    break
                
                print("\n🤖 系统:")
                result = qa_system.query(user_input)
                
                # 处理新的返回格式（字典或字符串）
                if isinstance(result, dict):
                    answer = result.get('answer', result)
                    print(answer)
                else:
                    print(result)
            
            except KeyboardInterrupt:
                print("\n\n⚠️ 程序被中断")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
    
    finally:
        qa_system.close()
        print("\n✅ 程序已安全退出")


if __name__ == "__main__":
    main()
