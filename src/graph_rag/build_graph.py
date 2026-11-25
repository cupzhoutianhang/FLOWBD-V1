"""
步骤四和步骤五：构建知识图谱和导入 Neo4j 数据库

该脚本完成以下功能：
1. 读取合并后的 JSON 文件（由步骤一、二、三生成）
2. 构建完整的知识图谱（步骤四）
3. 将知识图谱导入 Neo4j 数据库（步骤五）
"""

import os
import json
import re
from typing import Dict, List, Tuple
from neo4j import GraphDatabase, basic_auth


class KnowledgeGraphBuilder:
    """知识图谱构建器"""
    
    def __init__(self, merged_data_dir: str = None):
        """
        初始化知识图谱构建器
        
        Args:
            merged_data_dir: 合并后 JSON 文件所在目录。如果为None，使用默认的相对项目根目录的路径
        """
        if merged_data_dir is None:
            # 基于当前模块的相对路径
            merged_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
        self.merged_data_dir = merged_data_dir
        self.graph = {"nodes": {}, "edges": {}}
        self.node_counter = 0
        self.edge_counter = 0
        self.entity_id_mapping = {}  # 用于快速查找实体
        self.debug = False  # 调试模式标志
        
    def load_merged_files(self) -> Dict[str, Dict]:
        """
        加载所有合并后的 JSON 文件。
        优先加载最新的迭代改进版本（improved_merged或iteration_*_merged），
        否则加载基础的merged版本。
        返回包含数据和文件信息的字典。
        
        Returns:
            Dict: {doc_id: {"data": merged_data, "source_file": filename, "version": version_name}}
        """
        merged_docs = {}
        doc_files = {}  # {doc_id: {version: filename}}
        self.source_files_info = {}  # 用于存储源文件信息，供后续使用
        
        if not os.path.exists(self.merged_data_dir):
            print(f"错误：目录 {self.merged_data_dir} 不存在")
            return merged_docs
        
        print(f"\n正在扫描合并后的 JSON 文件...")
        
        # 第一步：扫描所有相关文件
        for filename in os.listdir(self.merged_data_dir):
            if "_merged.json" in filename:
                # 提取文档ID（去掉后缀）
                if filename.endswith("_improved_merged.json"):
                    doc_id = filename.replace("_improved_merged.json", "")
                    version = "improved"
                elif "_iteration_" in filename and filename.endswith("_merged.json"):
                    # 处理 iteration_N_merged.json 格式
                    match = re.match(r"(.+?)_iteration_(\d+)_merged\.json", filename)
                    if match:
                        doc_id = match.group(1)
                        iteration_num = int(match.group(2))
                        version = ("iteration", iteration_num)
                    else:
                        continue
                elif filename.endswith("_merged.json"):
                    doc_id = filename.replace("_merged.json", "")
                    version = "base"
                else:
                    continue
                
                # 初始化文档记录
                if doc_id not in doc_files:
                    doc_files[doc_id] = {}
                
                # 记录此文件
                doc_files[doc_id][version] = filename
        
        # 第二步：为每个文档选择最优版本
        print(f"\n正在加载文件...")
        for doc_id, versions in doc_files.items():
            # 优先级：improved > iteration_最大值 > base
            selected_filename = None
            selected_version = None
            
            if "improved" in versions:
                selected_filename = versions["improved"]
                selected_version = "improved"
            else:
                # 找到最大的iteration号
                iteration_versions = {}
                for version_key, filename in versions.items():
                    if isinstance(version_key, tuple) and version_key[0] == "iteration":
                        iteration_versions[version_key[1]] = filename
                
                if iteration_versions:
                    max_iteration = max(iteration_versions.keys())
                    selected_filename = iteration_versions[max_iteration]
                    selected_version = f"iteration_{max_iteration}"
                elif "base" in versions:
                    selected_filename = versions["base"]
                    selected_version = "base"
            
            if selected_filename:
                filepath = os.path.join(self.merged_data_dir, selected_filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    merged_docs[doc_id] = {
                        "data": data,
                        "source_file": selected_filename,
                        "version": selected_version
                    }
                    # 保存源文件信息
                    self.source_files_info[doc_id] = {
                        "filename": selected_filename,
                        "version": selected_version
                    }
                    print(f"  ✅ 加载: {selected_filename} [{selected_version}]")
                except Exception as e:
                    print(f"  ❌ 加载失败 {selected_filename}: {str(e)[:100]}")
        
        print(f"\n总计加载 {len(merged_docs)} 个文档的合并数据")
        return merged_docs
    
    def _deduplicate_triples(self, merged_docs: Dict[str, Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        对多个文件的 JSON 三元组进行去重
        三元组 = (实体名称, 实体类型, 属性key-value) 或 (源实体, 关系类型, 目标实体)
        
        Returns:
            Tuple: (去重后的实体列表, 去重后的关系列表)
        """
        # 使用集合记录已见的三元组
        seen_entities = set()  # (name, type) 元组
        seen_relations = set()  # (source, relation_type, target) 元组
        seen_properties = {}    # {(name, type): set(properties)}
        
        unique_entities = []    # 去重后的实体
        unique_relations = []    # 去重后的关系
        entity_properties_map = {}  # {(name, type): properties_dict}
        
        # 第一步：收集并去重所有实体
        for doc_id, doc_info in merged_docs.items():
            try:
                if isinstance(doc_info, dict) and "data" in doc_info:
                    doc_data = doc_info["data"]
                else:
                    doc_data = doc_info
                
                data = doc_data.get("data", {})
                entities = data.get("entities", [])
                
                for entity in entities:
                    entity_name = entity.get("name")
                    entity_type = entity.get("type", "Entity")
                    
                    if not entity_name:
                        continue
                    
                    # 构造实体三元组的唯一键
                    entity_key = (entity_name, entity_type)
                    
                    if entity_key not in seen_entities:
                        seen_entities.add(entity_key)
                        unique_entities.append(entity)
                        entity_properties_map[entity_key] = dict(entity)
                    else:
                        # 合并属性和别名
                        existing = entity_properties_map[entity_key]
                        if "aliases" in entity and "aliases" in existing:
                            # 合并别名，去重
                            merged_aliases = list(set(existing.get("aliases", []) + entity.get("aliases", [])))
                            existing["aliases"] = merged_aliases
            except Exception as e:
                if self.debug:
                    print(f"  处理实体去重失败 {doc_id}: {e}")
        
        # 第二步：收集并去重所有关系
        relation_source_map = {}  # {entity_name: entity_id} 用于关系处理
        
        # 先建立实体名称到ID的映射
        for entity in unique_entities:
            entity_id = entity.get("id")
            entity_name = entity.get("name")
            if entity_id and entity_name:
                relation_source_map[entity_name] = entity_id
        
        for doc_id, doc_info in merged_docs.items():
            try:
                if isinstance(doc_info, dict) and "data" in doc_info:
                    doc_data = doc_info["data"]
                else:
                    doc_data = doc_info
                
                data = doc_data.get("data", {})
                relations = data.get("relations", [])
                
                for relation in relations:
                    source_id = relation.get("source")
                    target_id = relation.get("target")
                    rel_type = relation.get("relation")
                    
                    if not all([source_id, target_id, rel_type]):
                        continue
                    
                    # 构造关系三元组的唯一键
                    relation_key = (source_id, rel_type, target_id)
                    
                    if relation_key not in seen_relations:
                        seen_relations.add(relation_key)
                        unique_relations.append(relation)
            except Exception as e:
                if self.debug:
                    print(f"  处理关系去重失败 {doc_id}: {e}")
        
        print(f"\n📊 三元组去重统计：")
        print(f"  - 原始实体总数: {sum(len(d.get('data', {}).get('entities', [])) for d in merged_docs.values() if isinstance(d, dict) and 'data' in d)}")
        print(f"  - 去重后实体数: {len(unique_entities)}")
        print(f"  - 原始关系总数: {sum(len(d.get('data', {}).get('relations', [])) for d in merged_docs.values() if isinstance(d, dict) and 'data' in d)}")
        print(f"  - 去重后关系数: {len(unique_relations)}")
        
        return unique_entities, unique_relations
    
    def build_graph(self, merged_docs: Dict[str, Dict]) -> None:
        """
        从合并的 JSON 数据构建知识图谱。
        将所有文本的最新JSON数据合并到一张图谱中。
        
        Args:
            merged_docs: 合并后的文档数据
        """
        print("\n=== 开始步骤四：构建知识图谱 ===")
        print(f"\n📊 构建多文本联合图谱（共 {len(merged_docs)} 个文本）")
        print("\n📄 使用的JSON文件信息：")
        
        # 显示使用的源文件信息
        for doc_id, file_info in self.source_files_info.items():
            print(f"  📋 {doc_id}")
            print(f"     └─ 文件: {file_info['filename']} [{file_info['version']}]")
        
        # 第一步：去重所有三元组
        print("\n[预处理] 三元组去重...")
        unique_entities, unique_relations = self._deduplicate_triples(merged_docs)
        
        total_entities = 0
        total_relations = 0
        
        # 【修复】第一步：创建所有节点，但不设置 source_docs
        for entity in unique_entities:
            entity_name = entity.get("name")
            entity_type = entity.get("type", "Entity")
            
            if not entity_name:
                continue
            
            # 检查实体是否已存在
            existing_node_id = None
            for node_id, node in self.graph["nodes"].items():
                if node["properties"].get("name") == entity_name and node["label"] == entity_type:
                    existing_node_id = node_id
                    break
            
            if not existing_node_id:
                # 创建新节点，先不设置 source_docs
                node_id = f"node_{self.node_counter}"
                self.node_counter += 1
                new_node = {
                    "id": node_id,
                    "label": entity_type,
                    "properties": {
                        "name": entity_name,
                        "source_docs": []  # 【改进】初始为空列表
                    }
                }
                # 添加额外属性
                if "aliases" in entity:
                    new_node["properties"]["aliases"] = entity["aliases"]
                
                self.graph["nodes"][node_id] = new_node
        
        # 【修复】第二步：遍历每个文档，为其中实际包含的实体/关系添加来源
        for doc_id, doc_info in merged_docs.items():
            try:
                # 获取实体和关系数据
                if isinstance(doc_info, dict) and "data" in doc_info:
                    doc_data = doc_info["data"]
                else:
                    doc_data = doc_info
                
                data = doc_data.get("data", {})
                entities_in_doc = data.get("entities", [])
                relations_in_doc = data.get("relations", [])
                
                # 建立此文档中实体的ID映射
                doc_entity_mapping = {}
                
                # 对此文档中的实体添加来源
                for entity_in_doc in entities_in_doc:
                    entity_id = entity_in_doc.get("id")
                    entity_name = entity_in_doc.get("name")
                    entity_type = entity_in_doc.get("type", "Entity")
                    
                    if not entity_name:
                        continue
                    
                    # 查找对应的节点
                    for node_id, node in self.graph["nodes"].items():
                        if node["properties"].get("name") == entity_name and node["label"] == entity_type:
                            # 【关键】只为实际出现在此文档中的实体添加来源
                            if doc_id not in node["properties"].get("source_docs", []):
                                node["properties"]["source_docs"].append(doc_id)
                            doc_entity_mapping[entity_id] = node_id
                            total_entities += 1
                            break
                
                # 对此文档中的关系添加来源
                for relation_in_doc in relations_in_doc:
                    source_id = relation_in_doc.get("source")
                    target_id = relation_in_doc.get("target")
                    rel_type = relation_in_doc.get("relation")
                    
                    if not all([source_id, target_id, rel_type]):
                        continue
                    
                    # 转换为实际的节点ID
                    source_node_id = doc_entity_mapping.get(source_id)
                    target_node_id = doc_entity_mapping.get(target_id)
                    
                    if not source_node_id or not target_node_id:
                        continue
                    
                    # 检查关系是否已存在
                    existing_edge = None
                    for edge_id, edge in self.graph["edges"].items():
                        if (edge["source"] == source_node_id and 
                            edge["target"] == target_node_id and 
                            edge["relationship"] == rel_type):
                            existing_edge = edge
                            break
                    
                    if not existing_edge:
                        # 创建新关系
                        edge_id = f"edge_{self.edge_counter}"
                        self.edge_counter += 1
                        new_edge = {
                            "id": edge_id,
                            "source": source_node_id,
                            "target": target_node_id,
                            "relationship": rel_type,
                            "properties": {"source_docs": [doc_id]}  # 【关键】只添加包含此关系的文献
                        }
                        self.graph["edges"][edge_id] = new_edge
                        total_relations += 1
                    else:
                        # 【关键】只为实际出现在此文档中的关系添加来源
                        if doc_id not in existing_edge["properties"].get("source_docs", []):
                            existing_edge["properties"]["source_docs"].append(doc_id)
                
            except Exception as e:
                print(f"  ❌ 处理文档 {doc_id} 失败: {str(e)[:100]}")
        
        print(f"\n图谱构建完成（多文本联合）:")
        print(f"  - 文本数量: {len(self.source_files_info)}")
        print(f"  - 节点总数: {len(self.graph['nodes'])}")
        print(f"  - 边总数: {len(self.graph['edges'])}")
        print(f"  - 处理的实体: {total_entities}")
        print(f"  - 处理的关系: {total_relations}")
    
    def export_graph_json(self, output_file: str = "knowledge_graph.json") -> None:
        """
        将知识图谱导出为 JSON 文件
        
        Args:
            output_file: 输出文件路径
        """
        print(f"\n正在将多文本联合图谱导出为 JSON 文件...")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 导出完成: {output_file}")
            print(f"     包含 {len(self.source_files_info)} 个文本的数据")
        except Exception as e:
            print(f"  ❌ 导出失败: {str(e)}")
    
    def analyze_graph(self) -> Dict:
        """
        分析知识图谱的统计信息
        
        Returns:
            Dict: 统计信息
        """
        print("\n=== 多文本联合图谱分析 ===")
        
        # 按类型统计实体
        entity_type_count = {}
        for node_id, node in self.graph["nodes"].items():
            label = node["label"]
            entity_type_count[label] = entity_type_count.get(label, 0) + 1
        
        # 按类型统计关系
        relationship_type_count = {}
        for edge_id, edge in self.graph["edges"].items():
            rel_type = edge["relationship"]
            relationship_type_count[rel_type] = relationship_type_count.get(rel_type, 0) + 1
        
        # 计算节点的度分布
        node_degree = {}
        for node_id in self.graph["nodes"]:
            node_degree[node_id] = 0
        
        for edge_id, edge in self.graph["edges"].items():
            node_degree[edge["source"]] += 1
            node_degree[edge["target"]] += 1
        
        # 输出统计信息
        print(f"\n基本统计：")
        print(f"  - 包含文本数: {len(self.source_files_info)}")
        print(f"  - 节点总数: {len(self.graph['nodes'])}")
        print(f"  - 边总数: {len(self.graph['edges'])}")
        avg_degree = sum(node_degree.values()) / len(node_degree) if node_degree else 0
        print(f"  - 平均度: {avg_degree:.2f}")
        
        print("\n实体类型分布:")
        for entity_type, count in sorted(entity_type_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {entity_type}: {count}")
        
        print("\n关系类型分布:")
        for rel_type, count in sorted(relationship_type_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {rel_type}: {count}")
        
        return {
            "node_count": len(self.graph["nodes"]),
            "edge_count": len(self.graph["edges"]),
            "entity_type_count": entity_type_count,
            "relationship_type_count": relationship_type_count,
            "avg_degree": avg_degree
        }


class Neo4jImporter:
    """Neo4j 数据库导入器"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", 
                 password: str = __import__("os").environ.get("NEO4J_PASSWORD", "")):
        """
        初始化 Neo4j 导入器
        
        Args:
            uri: Neo4j 数据库 URI
            user: 用户名
            password: 密码
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
    
    def connect(self) -> bool:
        """
        连接到 Neo4j 数据库
        
        Returns:
            bool: 是否连接成功
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=basic_auth(self.user, self.password),
                encrypted=False
            )
            # 验证连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✅ 成功连接到 Neo4j 数据库")
            return True
        except Exception as e:
            print(f"❌ 连接 Neo4j 失败: {str(e)}")
            return False
    
    def clear_database(self) -> bool:
        """
        清空数据库中的所有数据（谨慎使用！）
        
        Returns:
            bool: 是否清空成功
        """
        if not self.driver:
            print("错误：未连接到数据库")
            return False
        
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            print("✅ 已清空数据库")
            return True
        except Exception as e:
            print(f"❌ 清空数据库失败: {str(e)}")
            return False
    
    def import_graph(self, graph: Dict, clear_first: bool = False) -> bool:
        """
        将知识图谱导入 Neo4j
        
        Args:
            graph: 知识图谱数据 {"nodes": {...}, "edges": {...}}
            clear_first: 是否先清空数据库
        
        Returns:
            bool: 是否导入成功
        """
        if not self.driver:
            print("错误：未连接到数据库")
            return False
        
        try:
            print("\n=== 开始步骤五：导入 Neo4j 数据库 ===")
            
            if clear_first:
                print("正在清空现有数据...")
                self.clear_database()
            
            with self.driver.session() as session:
                # 第一步：导入节点
                print("正在导入节点...")
                node_count = 0
                for node_id, node_data in graph["nodes"].items():
                    try:
                        # 清理标签中的非法字符
                        raw_label = node_data.get("label", "Entity")
                        cleaned_label = re.sub(r'[^a-zA-Z0-9_]', '_', raw_label)
                        if cleaned_label and cleaned_label[0].isdigit():
                            cleaned_label = f"_{cleaned_label}"
                        
                        # 创建节点
                        cypher = (
                            f"CREATE (n:{cleaned_label} {{id: $node_id}}) "
                            f"SET n += $properties"
                        )
                        session.run(
                            cypher,
                            node_id=node_id,
                            properties=node_data["properties"]
                        )
                        node_count += 1
                    except Exception as e:
                        pass  # 不打印节点导入错误
                
                print(f"✅ 导入了 {node_count} 个节点")
                
                # 第二步：导入边
                print("正在导入关系...")
                edge_count = 0
                for edge_id, edge_data in graph["edges"].items():
                    try:
                        # 清理关系类型中的非法字符
                        cleaned_relationship = re.sub(r'[^a-zA-Z0-9_]', '_', edge_data['relationship'])
                        if cleaned_relationship and cleaned_relationship[0].isdigit():
                            cleaned_relationship = f"_{cleaned_relationship}"
                        
                        # 创建关系 - 使用优化的查询语法避免笛卡尔积警告
                        cypher = (
                            f"MATCH (a {{id: $source}}) "
                            f"MATCH (b {{id: $target}}) "
                            f"CREATE (a)-[r:{cleaned_relationship} {{id: $edge_id}}]->(b) "
                            f"SET r += $properties"
                        )
                        session.run(
                            cypher,
                            source=edge_data["source"],
                            target=edge_data["target"],
                            edge_id=edge_id,
                            properties=edge_data.get("properties", {})
                        )
                        edge_count += 1
                    except Exception as e:
                        pass  # 不打印关系导入错误
                
                print(f"✅ 导入了 {edge_count} 条关系")
            
            print("\n✅ 知识图谱成功导入 Neo4j 数据库")
            return True
            
        except Exception as e:
            print(f"❌ 导入失败: {str(e)}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            print("✅ 已关闭数据库连接")


def main():
    """主函数：完成步骤四和步骤五"""
    
    print("="*60)
    print("多文本知识图谱构建与 Neo4j 导入工具")
    print("="*60)
    
    # 步骤四：构建知识图谱
    print("\n【步骤四】构建知识图谱")
    print("-"*60)
    
    builder = KnowledgeGraphBuilder()  # 使用默认路径
    
    # 加载合并的 JSON 文件
    merged_docs = builder.load_merged_files()
    
    if not merged_docs:
        print("❌ 未找到合并后的 JSON 文件，请先运行 graph_rag.py 完成步骤一、二、三")
        return
    
    # 构建图谱
    builder.build_graph(merged_docs)
    
    # 导出为 JSON
    builder.export_graph_json("knowledge_graph.json")
    
    # 分析图谱
    stats = builder.analyze_graph()
    
    # 步骤五：导入 Neo4j
    print("\n【步骤五】导入 Neo4j 数据库")
    print("-"*60)
    
    # 配置 Neo4j 连接参数
    neo4j_config = {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": __import__("os").environ.get("NEO4J_PASSWORD", "")
    }
    
    importer = Neo4jImporter(**neo4j_config)
    
    # 尝试连接
    if importer.connect():
        # 导入图谱（可选：先清空数据库）
        import_success = importer.import_graph(builder.graph, clear_first=False)
        
        if import_success:
            print("\n✅ 步骤四和步骤五完成！")
            print("\n你现在可以在 Neo4j Browser 中访问知识图谱：")
            print("  1. 打开 http://localhost:7474/")
            print("  2. 输入查询语句查看节点和关系")
            print("  3. 示例查询:")
            print("     - MATCH (n) RETURN n LIMIT 100  # 查看前100个节点")
            print("     - MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50  # 查看关系")
        else:
            print("❌ 导入 Neo4j 失败")
        
        importer.close()
    else:
        print("❌ 无法连接到 Neo4j，请确保：")
        print("  1. Neo4j 服务正在运行")
        print("  2. 数据库 URI 正确（默认: bolt://localhost:7687）")
        print("  3. 用户名和密码正确（默认: neo4j/neo4j）")
        print("\n你可以修改脚本中的 neo4j_config 来更新连接参数")


if __name__ == "__main__":
    main()
