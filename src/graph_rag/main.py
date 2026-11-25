#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphRAG 完整流程主脚本

一站式执行 GraphRAG 的所有步骤：
1. 步骤一：实体提取 (Entity Extraction)
2. 步骤二：关系提取 (Relation Extraction)
3. 步骤三：合并JSON (Merge entities & relations)
4. 步骤四：自动检测和修改 (Validation & Repair Loop)
5. 步骤五：构建知识图谱 (Build Knowledge Graph)
6. 步骤六：导入Neo4j (Import to Neo4j)
"""

import os
import sys
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GRAPH_RAG_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, _GRAPH_RAG_DIR)

# 导入当前目录的模块
from graph_rag import GraphRAG
from build_graph import KnowledgeGraphBuilder, Neo4jImporter


def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_footer(title):
    """打印完成标记"""
    print("\n" + "-"*70)
    print(f"✅ {title}")
    print("-"*70)


def execute_graph_rag_extraction(data_directory):
    """
    执行 GraphRAG 的前三步：
    - 步骤一：实体提取
    - 步骤二：关系提取
    - 步骤三：合并JSON
    - 步骤四：自动检测和修改
    """
    print_header("开始 GraphRAG 提取流程（步骤一~四）")
    
    try:
        # 初始化 GraphRAG
        print("\n🔧 初始化 GraphRAG 系统...")
        graph_rag = GraphRAG(data_directory)
        
        # GraphRAG 的 __init__ 方法已经包含了步骤一到步骤四的完整流程
        # （在 _build_knowledge_graph 方法中）
        print("\n✅ GraphRAG 提取流程完成！")
        print(f"   合并后的JSON文件已保存至: src/llm_responses/")
        
        return True
        
    except Exception as e:
        print(f"\n❌ GraphRAG 提取流程失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def execute_graph_building(output_file="knowledge_graph.json"):
    """
    执行步骤五：构建知识图谱
    """
    print_header("开始步骤五：构建多文本联合知识图谱")
    
    try:
        # 初始化图谱构建器
        builder = KnowledgeGraphBuilder()
        
        # 加载合并的 JSON 文件
        print("\n📂 加载合并后的JSON文件...")
        merged_docs = builder.load_merged_files()
        
        if not merged_docs:
            print("❌ 未找到合并后的 JSON 文件")
            return False
        
        # 构建图谱
        print(f"\n🔗 构建多文本联合图谱（共 {len(merged_docs)} 个文本）...")
        builder.build_graph(merged_docs)
        
        # 导出为 JSON
        print(f"\n💾 导出图谱为 JSON 文件...")
        builder.export_graph_json(output_file)
        
        # 分析图谱
        print(f"\n📊 分析图谱统计信息...")
        stats = builder.analyze_graph()
        
        print_footer(f"步骤五完成！知识图谱已保存至: {output_file}")
        return builder, stats
        
    except Exception as e:
        print(f"\n❌ 图谱构建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def execute_neo4j_import(graph, neo4j_uri="bolt://localhost:7687", 
                         neo4j_user="neo4j", neo4j_password=__import__("os").environ.get("NEO4J_PASSWORD", ""), 
                         clear_first=False):
    """
    执行步骤六：导入 Neo4j 数据库
    """
    print_header("开始步骤六：导入 Neo4j 数据库")
    
    try:
        # 配置 Neo4j 连接参数
        neo4j_config = {
            "uri": neo4j_uri,
            "user": neo4j_user,
            "password": neo4j_password
        }
        
        print(f"\n🔗 连接 Neo4j 数据库...")
        print(f"   URI: {neo4j_uri}")
        print(f"   User: {neo4j_user}")
        
        importer = Neo4jImporter(**neo4j_config)
        
        # 尝试连接
        if not importer.connect():
            print("❌ 无法连接到 Neo4j，请确保：")
            print("   1. Neo4j 服务正在运行")
            print("   2. 数据库 URI 正确")
            print("   3. 用户名和密码正确")
            return False
        
        # 导入图谱
        print(f"\n📤 导入多文本联合图谱到 Neo4j...")
        import_success = importer.import_graph(graph, clear_first=clear_first)
        
        if import_success:
            print_footer("步骤六完成！知识图谱已成功导入 Neo4j")
            print("\n💡 你现在可以在 Neo4j Browser 中访问知识图谱：")
            print("   1. 打开 http://localhost:7474/")
            print("   2. 输入查询语句查看节点和关系")
            print("   3. 示例查询:")
            print("      - MATCH (n) RETURN n LIMIT 100")
            print("      - MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50")
            importer.close()
            return True
        else:
            print("❌ 导入 Neo4j 失败")
            importer.close()
            return False
            
    except Exception as e:
        print(f"\n❌ Neo4j 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数：执行完整的 GraphRAG 流程"""
    
    parser = argparse.ArgumentParser(
        description="GraphRAG 完整流程执行脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 执行完整流程（包括所有步骤）
  python main.py --data extraction_results
  
  # 只执行提取步骤（步骤一~四）
  python main.py --data extraction_results --extract-only
  
  # 只执行图谱构建和导入（步骤五~六）
  python main.py --graph-only
  
  # 自定义 Neo4j 连接参数
  python main.py --data extraction_results --neo4j-uri bolt://localhost:7688
  
  # 导入前清空 Neo4j 数据库
  python main.py --data extraction_results --clear-neo4j
        """)
    
    parser.add_argument(
        '--data',
        default='extraction_results',
        help='MD文件所在目录（默认: extraction_results）'
    )
    parser.add_argument(
        '--extract-only',
        action='store_true',
        help='只执行提取步骤（步骤一~四）'
    )
    parser.add_argument(
        '--graph-only',
        action='store_true',
        help='只执行图谱构建和导入（步骤五~六）'
    )
    parser.add_argument(
        '--output',
        default='knowledge_graph.json',
        help='输出的知识图谱 JSON 文件（默认: knowledge_graph.json）'
    )
    parser.add_argument(
        '--neo4j-uri',
        default='bolt://localhost:7687',
        help='Neo4j 数据库 URI（默认: bolt://localhost:7687）'
    )
    parser.add_argument(
        '--neo4j-user',
        default='neo4j',
        help='Neo4j 用户名（默认: neo4j）'
    )
    parser.add_argument(
        '--neo4j-password',
        default=__import__("os").environ.get("NEO4J_PASSWORD", ""),
        help='Neo4j 密码（默认: neo4j123）'
    )
    parser.add_argument(
        '--clear-neo4j',
        action='store_true',
        help='导入前清空 Neo4j 数据库'
    )
    parser.add_argument(
        '--skip-import',
        action='store_true',
        help='跳过 Neo4j 导入步骤'
    )
    
    args = parser.parse_args()
    
    # 打印开始信息
    print("\n" + "="*70)
    print("   GraphRAG 完整流程执行脚本")
    print("="*70)
    print(f"\n⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 第一阶段：提取步骤
    if not args.graph_only:
        print("\n【第一阶段】实体提取、关系提取、自动检测和修改")
        data_dir = os.path.join(PROJECT_ROOT, args.data) if not os.path.isabs(args.data) else args.data
        
        if not execute_graph_rag_extraction(data_dir):
            print("\n❌ 提取步骤失败，停止执行")
            return False
        
        if args.extract_only:
            print("\n✅ 提取步骤完成（只执行提取）")
            return True
    
    # 第二阶段：图谱构建步骤
    if not args.extract_only:
        result = execute_graph_building(args.output)
        if not result:
            print("\n❌ 图谱构建失败，停止执行")
            return False
        
        builder, stats = result
        
        # 第三阶段：Neo4j 导入步骤
        if not args.skip_import:
            success = execute_neo4j_import(
                builder.graph,
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password,
                clear_first=args.clear_neo4j
            )
            if not success:
                return False
    
    # 打印总体完成信息
    print("\n" + "="*70)
    print("   GraphRAG 完整流程执行完成！🎉")
    print("="*70)
    print(f"\n⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📊 输出文件:")
    print(f"   - 知识图谱 JSON: {args.output}")
    print(f"   - 合并 JSON: src/llm_responses/ (多个)")
    print(f"   - 验证报告: src/llm_responses/ (MD格式)")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 执行被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
