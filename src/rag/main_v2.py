"""
RAG V2 多轮对话系统 - 主入口

改进内容：
1. 优化分块策略（子块500字符）
2. 集成Reranker二次精排
3. 支持重建索引
4. 详细的调试输出

使用方法：
    首次运行（重建索引）：
        python main_v2.py --rebuild
    
    正常运行：
        python main_v2.py
    
    调试模式：
        python main_v2.py --debug
"""

import os
import sys
import argparse

# 添加项目根目录到Python路径
# main_v2.py 位于: D:\self_evolving_rag\src\agent\graphrag_and_rag\rag\main_v2.py
# 向上5级到项目根目录: D:\self_evolving_rag
# main_v2.py 位于 src/rag/main_v2.py，向上级退 2 次即可到达项目根目录 FlowBD系统
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='RAG V2 多轮对话系统')
    parser.add_argument('--rebuild', action='store_true', help='强制重建索引')
    parser.add_argument('--debug', action='store_true', help='开启调试模式')
    parser.add_argument('--top-k', type=int, default=5, help='召回父块数量 (默认: 5)')
    return parser.parse_args()


def main():
    args = parse_args()
    
    print("="*70)
    print("RAG V2 多轮对话系统启动")
    print("="*70)
    print(f"  重建索引: {'是' if args.rebuild else '否'}")
    print(f"  调试模式: {'是' if args.debug else '否'}")
    print(f"  召回数量: {args.top_k}")
    print("="*70)
    
    # 调试信息
    if args.debug:
        print(f"\n【调试信息】")
        print(f"  脚本位置: {__file__}")
        print(f"  工作目录: {os.getcwd()}")
        print(f"  PROJECT_ROOT: {PROJECT_ROOT}")
    
    # 模型路径
    # 修正模型路径，实际在 src/rag/models
    model_path = os.path.join(PROJECT_ROOT, "src", "rag", "models")
    data_path = os.path.join(PROJECT_ROOT, "pdf_to_md", "extraction_results")
    
    print(f"\n调试信息：")
    print(f"  PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"  model_path: {model_path}")
    print(f"  data_path: {data_path}")
    print()
    
    # 检查路径
    if not os.path.exists(model_path):
        print(f"✗ 模型路径不存在: {model_path}")
        print(f"  当前工作目录: {os.getcwd()}")
        print(f"  此脚本路径: {__file__}")
        sys.exit(1)
    
    if not os.path.exists(data_path):
        print(f"✗ 数据路径不存在: {data_path}")
        print(f"  当前工作目录: {os.getcwd()}")
        sys.exit(1)
    
    # ========== 步骤1: 初始化RAG系统（加载模型、构建索引）==========
    print("\n【步骤 1】正在初始化RAG V3系统...")
    
    from traditional_rag_v3 import TraditionalRAGV3
    
    rag_system = TraditionalRAGV3(
        data_directory=data_path,
        model_path=model_path,
        force_rebuild=args.rebuild
    )
    
    # 获取加载的模型
    models = rag_system.get_models()
    print("✓ RAG V3系统初始化成功")
    
    # ========== 步骤2: 初始化问答系统 ==========
    print("\n【步骤 2】正在初始化RAGQA V2系统...")
    
    from rag_qa_v2 import RAGQAV2
    
    qa_system = RAGQAV2(
        embedding_model=models['embedding_model'],
        embedding_tokenizer=models['embedding_tokenizer'],
        milvus_collection=models['milvus_collection'],
        reranker_model=models['reranker_model'],
        reranker_tokenizer=models['reranker_tokenizer'],
        document_titles=rag_system.document_titles,  # 传入文档标题映射
        debug=args.debug
    )
    print("✓ RAGQA V2系统初始化成功")
    
    # ========== 步骤3: 进入多轮对话 ==========
    print("\n" + "="*70)
    print("系统初始化完成，可以开始多轮对话")
    print("="*70)
    print("\n" + "="*70)
    print("进入多轮对话模式")
    print("="*70)
    print("提示: 输入 'exit' 或 'quit' 退出，输入 'history' 查看对话历史")
    print("="*70)
    
    history = []
    
    while True:
        try:
            query = input("\n请输入您的问题 (exit/quit 退出): ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit']:
                print("\n感谢使用，再见！")
                break
            
            if query.lower() == 'history':
                print("\n【对话历史】")
                if not history:
                    print("  暂无对话记录")
                else:
                    for i, (q, a) in enumerate(history, 1):
                        print(f"  {i}. Q: {q[:50]}...")
                        print(f"     A: {a[:100]}...")
                continue
            
            print(f"\n【用户查询】{query}")
            print("-"*70)
            
            # 调用问答系统
            result = qa_system.answer_query(query, top_k=args.top_k)
            
            # 输出答案
            print(f"\n【大模型答案】")
            print(result['answer'])
            
            # 输出检索信息
            if result['parent_blocks']:
                print(f"\n【检索信息】")
                print(f"召回父块数: {len(result['parent_blocks'])}")
                for i, block in enumerate(result['parent_blocks'], 1):
                    rerank_score = block.get('rerank_score', 'N/A')
                    if isinstance(rerank_score, float):
                        print(f"  {i}. 父块ID: {block['parent_id']}, "
                              f"向量分: {block.get('max_similarity', 0):.4f}, "
                              f"Rerank分: {rerank_score:.4f}")
                    else:
                        print(f"  {i}. 父块ID: {block['parent_id']}")
            
            print(f"\n【置信度】{result['confidence']}")
            
            # 保存到历史
            history.append((query, result['answer']))
            
        except KeyboardInterrupt:
            print("\n\n检测到中断，退出程序...")
            break
        except Exception as e:
            print(f"\n处理查询时出错: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
