import json
import os
import re
from neo4j import GraphDatabase, basic_auth, exceptions
from tqdm import tqdm
from typing import Dict, Tuple, Set

class OptimizedDataNeo4jImporter:
    """优化数据专属导入器（处理跨文件实体重复问题）"""
    def __init__(self, uri, user, password, batch_size=2000):
        # 优化数据专属配置（核心隔离标识）
        self.isolation_label = "OptimizedData"  # 优化数据专属标签
        self.isolation_attr = "data_type: 'opt'"  # 优化数据专属属性
        self.node_prefix = "opt_"  # 优化节点前缀
        self.rel_prefix = "opt_"   # 优化关系前缀

        # Neo4j连接配置
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.batch_size = batch_size
        self.node_cache: Set[str] = set()  # 存储唯一键而非ID，避免重复导入节点
        self.db_node_cache_initialized = False  # 数据库缓存初始化标志

    def connect(self):
        """连接Neo4j（优化数据专属账号）"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=basic_auth(self.user, self.password),
                encrypted=False,
                max_connection_pool_size=50
            )
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✅ 优化数据导入器 - 连接Neo4j成功")
            # 连接成功后初始化数据库缓存
            self._init_db_node_cache()
            return True
        except exceptions.ServiceUnavailable:
            print("❌ 优化数据导入器 - 数据库未启动，请检查Neo4j服务")
            return False
        except exceptions.AuthError:
            print("❌ 优化数据导入器 - 账号密码错误")
            return False
        except Exception as e:
            print(f"❌ 优化数据导入器 - 连接失败: {str(e)[:100]}")
            return False

    def _init_db_node_cache(self):
        """从数据库初始化节点缓存（基于唯一键）"""
        if not self.driver or self.db_node_cache_initialized:
            return
        try:
            with self.driver.session() as session:
                # 查询已存在的优化数据节点的唯一键
                result = session.run(
                    f"MATCH (n:{self.isolation_label}) RETURN n.unique_key AS unique_key LIMIT 100000"
                )
                for record in result:
                    unique_key = record["unique_key"]
                    if unique_key:
                        self.node_cache.add(unique_key)
            self.db_node_cache_initialized = True
            print(f"📦 数据库缓存初始化完成，已有 {len(self.node_cache)} 个唯一实体")
        except Exception as e:
            print(f"⚠️ 数据库缓存初始化失败: {str(e)[:100]}，将使用内存缓存")

    def _clean_label(self, label):
        """清理标签非法字符，叠加优化数据前缀"""
        cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', label or "Entity")
        cleaned = f"_{cleaned}" if cleaned and cleaned[0].isdigit() else cleaned
        return f"{self.node_prefix}{cleaned}"

    def _clean_relation(self, rel_type):
        """清理关系类型，叠加优化数据前缀"""
        cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type or "REL")
        cleaned = f"_{cleaned}" if cleaned and cleaned[0].isdigit() else cleaned
        return f"{self.rel_prefix}{cleaned}"

    def batch_import_nodes(self, session, nodes_batch: list) -> int:
        """批量导入优化节点（保留原始类型标签）"""
        if not nodes_batch:
            return 0
        try:
            # 逐个插入节点以保留原始entity_type标签
            count = 0
            for node in nodes_batch:
                entity_type = node["properties"].get("entity_type", "Entity")
                clean_type = self._escape_label(entity_type)
                
                cypher = f"""
                    CREATE (n:{self.isolation_label}:`{clean_type}` {{id: $id}})
                    SET n += $properties, n.data_type = 'opt'
                """
                session.run(cypher, id=node["id"], properties=node["properties"])
                count += 1
            return count
        except Exception as e:
            print(f"\n⚠️ 优化节点批量导入失败: {str(e)[:100]}")
            if "already exists" in str(e).lower():
                print(f"   提示: 节点ID不唯一。请检查数据是否重复")
            return 0

    def _escape_label(self, label: str) -> str:
        """清理标签非法字符（保留原始类型名）"""
        cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', label or "Entity")
        cleaned = f"_{cleaned}" if cleaned and cleaned[0].isdigit() else cleaned
        return cleaned

    def batch_import_edges(self, session, edges_batch: list) -> int:
        """批量导入优化关系（带节点存在性检查）"""
        if not edges_batch:
            return 0
        try:
            rel_type = edges_batch[0]["rel"]
            cypher = f"""
                UNWIND $batch AS edge
                MATCH (a:{self.isolation_label} {{id: edge.source}}) 
                MATCH (b:{self.isolation_label} {{id: edge.target}})
                CREATE (a)-[r:`{rel_type}` {{id: edge.id}}]->(b)
                SET r += edge.properties, r.data_type = 'opt'
            """
            session.run(cypher, batch=edges_batch)
            return len(edges_batch)
        except Exception as e:
            error_msg = str(e).lower()
            print(f"\n⚠️ 优化关系批量导入失败: {str(e)[:100]}")
            if "no changes" in error_msg or "not found" in error_msg:
                print(f"   提示: 节点不存在。请确保节点已提前导入")
            return 0

    def import_single_opt_file(self, file_path: str, session) -> Tuple[int, int]:
        """导入单个优化数据JSON文件（基于类型+名称的复合唯一键去重）"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)

            # 提取data中的entities和relations
            data = graph.get("data", {})
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            
            # 【新增】从文件名提取来源文档信息
            file_basename = os.path.basename(file_path)
            # 支持多种格式：document_merged.json -> "document", document_iteration_1_merged.json -> "document"
            source_doc = file_basename.replace('_merged.json', '').replace('.json', '')
            if '_iteration_' in source_doc:
                source_doc = source_doc.split('_iteration_')[0]
            if '_v' in source_doc and source_doc[-3] != '_':
                source_doc = source_doc.rsplit('_v', 1)[0]

            # 1. 处理节点（基于类型+名称的复合唯一键去重）
            nodes_by_label = {}
            duplicated_nodes = 0  # 统计重复的节点
            file_node_unique_keys = set()  # 同文件内的唯一键缓存
            id_to_unique_key = {}  # 当前文件中ID与唯一键的映射

            for entity in entities:
                entity_id = entity.get("id")
                entity_type = entity.get("type", "Entity")
                entity_name = entity.get("name", "").strip()
                
                if not entity_id or not entity_name:
                    continue  # 过滤缺少关键信息的实体
                
                # 生成复合唯一键 (类型+名称)
                unique_key = f"{entity_type}::{entity_name}"
                id_to_unique_key[entity_id] = unique_key  # 记录ID与唯一键的映射
                
                # 检查同文件内重复
                if unique_key in file_node_unique_keys:
                    duplicated_nodes += 1
                    continue
                file_node_unique_keys.add(unique_key)
                
                # 检查跨文件重复（基于唯一键而非ID）
                if unique_key in self.node_cache:
                    duplicated_nodes += 1
                    continue
                self.node_cache.add(unique_key)
                
                clean_label = self._clean_label(entity_type)
                if clean_label not in nodes_by_label:
                    nodes_by_label[clean_label] = []
                
                # 【重要】添加source_docs属性
                nodes_by_label[clean_label].append({
                    "id": f"{self.node_prefix}{entity_id}",  # 保留原始ID作为节点ID
                    "label": clean_label,
                    "properties": {
                        "name": entity_name,
                        "entity_id": entity_id,  # 保留原始ID便于追溯
                        "entity_type": entity_type,
                        "unique_key": unique_key,  # 存储唯一键用于数据一致性检查
                        "source_docs": source_doc  # 【新增】来源文档
                    }
                })
            # ... existing code ...
            node_count = 0
            for label, nodes in nodes_by_label.items():
                for i in range(0, len(nodes), self.batch_size):
                    batch = nodes[i:i+self.batch_size]
                    node_count += self.batch_import_nodes(session, batch)

            # 2. 处理关系（使用唯一键验证节点存在性）
            edges_by_rel = {}
            skipped_relations = 0  # 统计因源/目标节点不存在而跳过的关系
            relation_cache = set()  # 用(源唯一键, 关系类型, 目标唯一键)去重

            for idx, relation in enumerate(relations):
                source_id = relation.get("source")
                target_id = relation.get("target")
                rel_type = relation.get("relation", "REL")
                
                # 转换为唯一键
                source_key = id_to_unique_key.get(source_id)
                target_key = id_to_unique_key.get(target_id)
                
                if not source_key or not target_key:
                    skipped_relations += 1
                    continue
                
                # 检查源目标节点是否存在（基于唯一键）
                if source_key not in self.node_cache or target_key not in self.node_cache:
                    skipped_relations += 1
                    continue
                
                # 关系去重（基于唯一键组合）
                rel_unique_key = (source_key, rel_type, target_key)
                if rel_unique_key in relation_cache:
                    skipped_relations += 1
                    continue
                relation_cache.add(rel_unique_key)
                
                clean_rel = self._clean_relation(rel_type)
                if clean_rel not in edges_by_rel:
                    edges_by_rel[clean_rel] = []
                
                edges_by_rel[clean_rel].append({
                    "id": f"{self.rel_prefix}{source_id}_{rel_type}_{target_id}_{idx}",
                    "source": f"{self.node_prefix}{source_id}",
                    "target": f"{self.node_prefix}{target_id}",
                    "properties": {
                        "relation": rel_type,
                        "source_key": source_key,
                        "target_key": target_key
                    },
                    "rel": clean_rel
                })

            # 批量导入关系
            edge_count = 0
            for rel, edges in edges_by_rel.items():
                for i in range(0, len(edges), self.batch_size):
                    batch = edges[i:i+self.batch_size]
                    edge_count += self.batch_import_edges(session, batch)

            # 输出文件级统计
            if duplicated_nodes > 0 or skipped_relations > 0:
                print(f"   ℹ️  {os.path.basename(file_path)}: 去重节点 {duplicated_nodes} 个，跳过关系 {skipped_relations} 条")
            
            return node_count, edge_count

        except json.JSONDecodeError as e:
            print(f"\n❌ JSON解析错误 {file_path}: {str(e)[:100]}")
            return 0, 0
        except KeyError as e:
            print(f"\n❌ 缺少必要字段 {file_path}: {str(e)[:100]}")
            return 0, 0
        except Exception as e:
            print(f"\n❌ 处理优化文件失败 {file_path}: {str(e)[:100]}")
            return 0, 0

    def _get_latest_json_per_document(self, opt_json_dir: str) -> Dict[str, str]:
        """获取每个文档的最新JSON文件（支持多次迭代）"""
        if not os.path.exists(opt_json_dir):
            print(f"❌ 路径不存在: {opt_json_dir}")
            return {}

        # 获取所有JSON文件
        json_files = [f for f in os.listdir(opt_json_dir) if f.endswith(".json")]
        if not json_files:
            print(f"⚠️ 未找到JSON文件: {opt_json_dir}")
            return {}

        # 按文档分组，每个文档保留最新版本
        latest_files = {}
        for filename in json_files:
            # 提取文档名（支持多种版本格式）
            # 格式1: document_iteration_N_merged.json -> (document, N)
            # 格式2: document_merged.json -> (document, 0)
            # 格式3: document_vN.json -> (document, N)
            match = re.match(r"^(.+?)(?:_iteration_(\d+))?(?:_v(\d+))?_merged\.json$|^(.+?)(?:_v(\d+))?\.json$", filename)
            if not match:
                continue
            
            # 提取文档名
            if filename.endswith("_merged.json"):
                # 处理 _iteration_N_merged.json 或 _merged.json
                doc_name = filename.replace("_merged.json", "")
                # 提取 iteration 号
                iteration_match = re.search(r"_iteration_(\d+)$", doc_name)
                if iteration_match:
                    version = int(iteration_match.group(1))
                    doc_name = doc_name.replace(f"_iteration_{version}", "")
                else:
                    version = 0
            else:
                # 处理 _vN.json 格式
                match = re.match(r"^(.+?)(?:_v(\d+))?\.json$", filename)
                if not match:
                    continue
                doc_name = match.group(1)
                version = int(match.group(2)) if match.group(2) else 0
            
            file_path = os.path.join(opt_json_dir, filename)
            
            # 对比版本号，保留最大版本
            if doc_name not in latest_files:
                latest_files[doc_name] = file_path
            else:
                # 提取现有文件的版本号进行比较
                existing_version = self._extract_version_smart(latest_files[doc_name])
                if version > existing_version:
                    latest_files[doc_name] = file_path

        return latest_files

    def _extract_version_smart(self, file_path: str) -> int:
        """
        智能提取版本号（支持多种格式）
        _iteration_N_merged.json -> N
        _vN.json -> N
        _merged.json -> 0
        """
        filename = os.path.basename(file_path)
        
        # 尝试提取 iteration 号
        iteration_match = re.search(r"_iteration_(\d+)_merged\.json$", filename)
        if iteration_match:
            return int(iteration_match.group(1))
        
        # 尝试提取 v 号
        v_match = re.search(r"_v(\d+)\.json$", filename)
        if v_match:
            return int(v_match.group(1))
        
        # 默认版本
        return 0

    def clear_database(self, confirm=True) -> bool:
        """清空数据库中的所有优化数据"""
        if not self.driver:
            print("❌ 未连接数据库，无法清空数据")
            return False

        if confirm:
            print("\n⚠️  警告：即将删除数据库中所有OptimizedData标签的节点和关系！")
            user_input = input("确认清空？(yes/no): ").strip().lower()
            if user_input != 'yes':
                print("❌ 已取消清空操作")
                return False

        try:
            with self.driver.session() as session:
                print("🗑️  开始清空优化数据...")
                
                # 1. 删除所有OptimizedData节点的关系
                result = session.run(
                    f"MATCH (n:{self.isolation_label})-[r]-() DELETE r RETURN count(r) AS count"
                )
                record = result.single()
                rel_count = record["count"] if record else 0
                print(f"   ✅ 已删除关系: {rel_count} 条")
                
                # 2. 删除所有OptimizedData节点
                result = session.run(
                    f"MATCH (n:{self.isolation_label}) DELETE n RETURN count(n) AS count"
                )
                record = result.single()
                node_count = record["count"] if record else 0
                print(f"   ✅ 已删除节点: {node_count} 个")
                
                # 3. 清空缓存
                self.node_cache.clear()
                self.db_node_cache_initialized = False
                
                print(f"\n✅ 数据库清空完成！删除节点 {node_count} 个，关系 {rel_count} 条")
                return True
        except Exception as e:
            print(f"\n❌ 清空数据库失败: {str(e)[:100]}")
            return False

    def import_all_opt_files(self, opt_json_dir: str, clear_first=False):
        """导入所有最新优化数据JSON文件（两阶段：先导入所有节点，再导入关系）"""
        if not self.driver:
            print("❌ 未连接数据库，无法导入优化数据")
            return

        # 选择性清空数据库
        if clear_first:
            self.clear_database(confirm=False)

        # 获取每个文档的最新JSON文件
        latest_files = self._get_latest_json_per_document(opt_json_dir)
        if not latest_files:
            print("⚠️ 未找到任何JSON文件")
            return

        print(f"📂 找到 {len(latest_files)} 个文档的最新版本")
        print(f"\n【阶段1】导入所有节点...")
        
        # 第一阶段：导入所有节点，构建全局ID映射
        total_nodes = 0
        all_relations = []  # 收集所有关系待后续处理
        global_id_to_unique_key = {}  # 全局ID→唯一键映射
        duplicated_sources_to_add = []  # 收集跨文件重复实体的来源，待后更新
        
        with self.driver.session() as session, tqdm(total=len(latest_files), desc="节点导入进度") as pbar:
            for doc_name, file_path in latest_files.items():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        graph = json.load(f)
                    
                    data = graph.get("data", {})
                    entities = data.get("entities", [])
                    relations = data.get("relations", [])
                    
                    # 处理节点并构建本文件的ID映射
                    file_node_unique_keys = set()
                    file_id_to_unique_key = {}
                    nodes_by_label = {}
                    
                    for entity in entities:
                        entity_id = entity.get("id")
                        entity_type = entity.get("type", "Entity")
                        entity_name = entity.get("name", "").strip()
                        
                        if not entity_id or not entity_name:
                            continue
                        
                        unique_key = f"{entity_type}::{entity_name}"
                        file_id_to_unique_key[entity_id] = unique_key
                        
                        # 检查同文件内重复
                        if unique_key in file_node_unique_keys:
                            continue
                        file_node_unique_keys.add(unique_key)
                        
                        # 【修复】检查跨文件重复
                        if unique_key in self.node_cache:
                            # 跨文件重复，不是第一次出现的实体
                            # 【关键】仅记录ID映射，不创建新节点，并且不更新source_docs
                            # 原因：数据库中已经有了该实体，其source_docs是第一次出现时设置的
                            # 如果需要追加新的第二个source_docs，应该在第三阶段处理
                            global_id_to_unique_key[entity_id] = unique_key
                            continue
                        
                        self.node_cache.add(unique_key)
                        global_id_to_unique_key[entity_id] = unique_key
                        
                        clean_label = self._clean_label(entity_type)
                        if clean_label not in nodes_by_label:
                            nodes_by_label[clean_label] = []
                        
                        # 【改进】设置source_docs为空列表，并然会在第三阶段中充实
                        nodes_by_label[clean_label].append({
                            "id": f"{self.node_prefix}{entity_id}",
                            "label": clean_label,
                            "properties": {
                                "name": entity_name,
                                "entity_id": entity_id,
                                "entity_type": entity_type,
                                "unique_key": unique_key,
                                "source_docs": [os.path.basename(file_path).replace('_merged.json', '').replace('.json', '').split('_iteration_')[0].rsplit('_v', 1)[0]]  # 改为列表
                            }
                        })
                        
                        # 【上丢】不再需要需要收集跨文件重复实体的来源戳
                        # 【下章：需需要添加第三阶段1
                        # 第三阶段应还处理跨文件重复实体的source_docs更新
                    
                    # 批量导入节点
                    for label, nodes in nodes_by_label.items():
                        for i in range(0, len(nodes), self.batch_size):
                            batch = nodes[i:i+self.batch_size]
                            total_nodes += self.batch_import_nodes(session, batch)
                    
                    # 收集关系（用全局ID映射）
                    for relation in relations:
                        source_id = relation.get("source")
                        target_id = relation.get("target")
                        rel_type = relation.get("relation", "REL")
                        
                        all_relations.append({
                            "source_id": source_id,
                            "target_id": target_id,
                            "rel_type": rel_type
                        })
                    
                    # 【上丢提不收集跨文件重复实体的来源信息、下章待追加】收集仅是第一次出现的实体的来源
                    # 检查跨文件重复实体的来源，为了后裸更新
                    for entity in entities:
                        entity_id = entity.get("id")
                        entity_type = entity.get("type", "Entity")
                        entity_name = entity.get("name", "").strip()
                        
                        if not entity_id or not entity_name:
                            continue
                        
                        unique_key = f"{entity_type}::{entity_name}"
                        
                        # 仅收集跨文件重复实体的来源
                        if unique_key in file_node_unique_keys:
                            continue
                        if unique_key not in self.node_cache:  # 仅收集跨文件重复的，不是第一次出现的
                            continue
                        
                        # 跨文件重复，需要追加source_docs
                        source_doc_to_add = os.path.basename(file_path).replace('_merged.json', '').replace('.json', '').split('_iteration_')[0].rsplit('_v', 1)[0]
                        duplicated_sources_to_add.append({
                            "unique_key": unique_key,
                            "source_doc": source_doc_to_add
                        })
                    
                    pbar.update(1)
                    pbar.set_description(f"节点导入 - 已导入: {total_nodes} 个")
                    
                except Exception as e:
                    print(f"\n❌ 处理文件失败 {os.path.basename(file_path)}: {str(e)[:100]}")
                    pbar.update(1)
        
        print(f"✅ 节点导入完成: {total_nodes} 个")
        
        # 第二阶段：使用全局ID映射导入所有关系
        print(f"\n【阶段2】导入所有关系...")
        total_edges = self._import_relations_global(all_relations, global_id_to_unique_key)
        
        # 第三阶段：为跨文件重复实体更新source_docs
        print(f"\n【阶段3】更新跨文件重复实体的来源...")
        self._update_duplicated_entity_sources(duplicated_sources_to_add)
        
        # 输出最终统计
        print(f"\n🎉 优化数据导入完成!")
        print(f"📊 统计：共处理 {len(latest_files)} 个文档，导入节点 {total_nodes} 个，关系 {total_edges} 条")


    def _import_relations_global(self, all_relations: list, global_id_to_unique_key: dict) -> int:
        """使用全局ID映射导入所有关系（支持跨文件关系）"""
        if not all_relations or not self.driver:
            return 0
        
        edge_count = 0
        edges_by_rel = {}
        skipped_count = 0
        relation_cache = set()
        
        try:
            with self.driver.session() as session:
                for relation in all_relations:
                    source_id = relation.get("source_id")
                    target_id = relation.get("target_id")
                    rel_type = relation.get("rel_type", "REL")
                    
                    # 使用全局映射（支持跨文件）
                    source_key = global_id_to_unique_key.get(source_id)
                    target_key = global_id_to_unique_key.get(target_id)
                    
                    if not source_key or not target_key:
                        skipped_count += 1
                        continue
                    
                    # 关系去重（基于唯一键组合）
                    rel_unique_key = (source_key, rel_type, target_key)
                    if rel_unique_key in relation_cache:
                        skipped_count += 1
                        continue
                    relation_cache.add(rel_unique_key)
                    
                    # 整理关系
                    clean_rel = self._clean_relation(rel_type)
                    if clean_rel not in edges_by_rel:
                        edges_by_rel[clean_rel] = []
                    
                    edges_by_rel[clean_rel].append({
                        "id": f"{self.rel_prefix}{source_id}_{rel_type}_{target_id}",
                        "source": f"{self.node_prefix}{source_id}",
                        "target": f"{self.node_prefix}{target_id}",
                        "properties": {
                            "relation": rel_type,
                            "source_key": source_key,
                            "target_key": target_key
                        },
                        "rel": clean_rel
                    })
                
                # 批量导入关系
                with tqdm(total=len(edges_by_rel), desc="关系导入进度", leave=False) as pbar:
                    for rel, edges in edges_by_rel.items():
                        for i in range(0, len(edges), self.batch_size):
                            batch = edges[i:i+self.batch_size]
                            edge_count += self.batch_import_edges(session, batch)
                        pbar.update(1)
                
                if skipped_count > 0:
                    print(f"   ⚠️ 跳过关系 {skipped_count} 条（节点未找到或重复）")
        
        except Exception as e:
            print(f"❌ 导入关系失败: {str(e)[:100]}")
        
        return edge_count

    def _update_duplicated_entity_sources(self, duplicated_sources_to_add: list) -> None:
        """为跨文件重复实体更新source_docs"""
        if not duplicated_sources_to_add or not self.driver:
            print(f"   ✅ 没有跨文件重复实体，无需更新")
            return
        
        # 合并并去重复
        sources_to_update = {}
        for item in duplicated_sources_to_add:
            unique_key = item["unique_key"]
            source_doc = item["source_doc"]
            
            if unique_key not in sources_to_update:
                sources_to_update[unique_key] = set()
            sources_to_update[unique_key].add(source_doc)
        
        # 更新Neo4j中的节点
        try:
            with self.driver.session() as session:
                for unique_key, sources_to_add in sources_to_update.items():
                    # 查询节点是否存在及其当前的source_docs
                    cypher_query = f"""
                    MATCH (n:{self.isolation_label})
                    WHERE n.unique_key = $unique_key
                    RETURN n.id AS node_id, n.source_docs AS current_sources
                    """
                    result = session.run(cypher_query, unique_key=unique_key)
                    record = result.single()
                    
                    if record:
                        node_id = record["node_id"]
                        current_sources = record["current_sources"] or []
                        # 确保是列表
                        if isinstance(current_sources, str):
                            current_sources = [current_sources]
                        
                        # 合并组织
                        updated_sources = list(set(current_sources) | sources_to_add)
                        
                        # 更新source_docs
                        cypher_update = f"""
                        MATCH (n:{self.isolation_label})
                        WHERE n.id = $node_id
                        SET n.source_docs = $updated_sources
                        """
                        session.run(cypher_update, node_id=node_id, updated_sources=updated_sources)
        
        except Exception as e:
            print(f"   ⚠️ 更新跨文件重复实体的source_docs失败: {str(e)[:100]}")
            return
        
        print(f"   ✅ 已更新 {len(sources_to_update)} 个跨文件重复实体的source_docs")

    def close(self):
        if self.driver:
            self.driver.close()
            print("✅ 优化数据导入器 - 已关闭数据库连接")

def main_opt_importer():
    # 配置项（请根据实际环境修改）
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_OPT_USER = "neo4j"  # 替换为实际用户名
    NEO4J_OPT_PWD = __import__("os").environ.get("NEO4J_PASSWORD", "")   # 替换为实际密码
    
    # JSON文件目录配置
    script_dir = os.path.dirname(os.path.abspath(__file__))
    LLM_RESPONSES_DIR = os.path.join(script_dir, "llm_responses")
    BATCH_SIZE = 2000
    CLEAR_BEFORE_IMPORT = True  # 导入前是否清空数据库

    # 初始化并运行导入器
    importer = OptimizedDataNeo4jImporter(NEO4J_URI, NEO4J_OPT_USER, NEO4J_OPT_PWD, BATCH_SIZE)
    if importer.connect():
        importer.import_all_opt_files(LLM_RESPONSES_DIR, clear_first=CLEAR_BEFORE_IMPORT)
        importer.close()
    else:
        print("❌ 无法连接到Neo4j数据库，请检查配置")

if __name__ == "__main__":
    main_opt_importer()