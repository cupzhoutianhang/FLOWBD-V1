"""
分子性质查询工具与 Agentic RAG 系统集成示例

展示如何将 MoleculePropertyTool 集成到现有的:
1. KnowledgeArsenal (Part 1)
2. IntegratedQASystem (Part 1 Integration)
3. Agent 框架

支持的增强场景：
- 当用户问到特定分子时，自动查询其性质
- 将分子性质作为额外上下文融合到 RAG 检索结果中
- 支持分子名称和 SMILES 的双向解析
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple

# 确保模块路径正确
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from molecule_property_tool import (
    MoleculePropertyTool,
    MoleculeQueryAgent,
    MoleculeQueryResult,
    RFBMoleculeLibrary,
    integrate_with_arsenal
)

logger = logging.getLogger(__name__)


class EnhancedIntegratedQASystem:
    """增强版集成问答系统 - 支持分子性质查询
    
    在原有 IntegratedQASystem 基础上增加:
    1. 分子性质自动查询
    2. 分子上下文与文档上下文融合
    3. 电化学相关问题的增强回答
    """
    
    def __init__(self,
                 api_key: str = None,
                 md_folder: str = None,
                 enable_deepchem: bool = True,
                 **kwargs):
        """初始化增强版问答系统
        
        Args:
            api_key: Kimi API密钥
            md_folder: Markdown文件夹路径
            enable_deepchem: 是否启用 DeepChem (需要安装)
            **kwargs: 传递给原 IntegratedQASystem 的其他参数
        """
        
        print("\n" + "="*80)
        print("🔧 初始化增强版问答系统 (RAG + Graph RAG + 分子性质查询)")
        print("="*80 + "\n")
        
        # 注意：这里假设你已经有原来的系统组件
        # 实际使用时需要导入你的 part1_knowledge_arsenal 和 part1_integration
        
        self.api_key = api_key
        self.md_folder = md_folder
        
        # 初始化分子查询工具
        print("[1/3] 初始化分子性质查询工具...")
        self.molecule_tool = MoleculePropertyTool(enable_deepchem=enable_deepchem)
        self.molecule_agent = MoleculeQueryAgent(enable_deepchem=enable_deepchem)
        print("  ✓ 分子性质查询工具就绪")
        
        # 初始化 RFB 分子库统计
        self._print_molecule_library_stats()
        
        # 原系统组件占位 (实际使用时替换为真实组件)
        self.llm = None
        self.arsenal = None
        self.parsing_agent = None
        self.doc_retrieval_agent = None
        self.graph_retrieval_agent = None
        self.fusion_agent = None
        self.answer_agent = None
        
        print("\n✅ 增强版系统初始化完成\n")
    
    def _print_molecule_library_stats(self):
        """打印分子库统计"""
        lib = self.molecule_tool.rfb_library
        print(f"\n  📚 RFB分子库统计:")
        print(f"    • 负极材料 (Anolyte): {len(lib.anolyte_molecules)} 种")
        print(f"    • 正极材料 (Catholyte): {len(lib.catholyte_molecules)} 种")
        print(f"    • 金属离子: {len(lib.metal_redox_species)} 种")
        print(f"    • 支持电解质: {len(lib.supporting_electrolytes)} 种")
        print(f"    • 溶剂: {len(lib.solvents)} 种")
        print(f"    • 添加剂: {len(lib.additives)} 种")
    
    def init_from_arsenal(self, arsenal):
        """从现有的 KnowledgeArsenal 初始化
        
        Args:
            arsenal: KnowledgeArsenal 实例
        """
        self.arsenal = arsenal
        self.llm = arsenal.get_llm()
        
        # 将分子查询工具集成到 arsenal
        integrate_with_arsenal(arsenal, enable_deepchem=True)
        
        # 更新 molecule_agent 的 LLM
        self.molecule_agent.llm = self.llm
        
        logger.info("✓ 已从 KnowledgeArsenal 初始化")
    
    def query(self, 
              question: str, 
              top_k: int = 5,
              include_molecule_context: bool = True) -> Dict[str, Any]:
        """执行增强查询
        
        Args:
            question: 用户问题
            top_k: 检索文档数量
            include_molecule_context: 是否包含分子性质上下文
            
        Returns:
            增强的查询结果
        """
        
        print(f"\n{'='*80}")
        print(f"【查询】{question}")
        print('='*80)
        
        result = {
            "question": question,
            "molecule_context": "",
            "molecule_results": [],
            "doc_context": "",
            "graph_context": "",
            "answer": "",
            "confidence": 0.0
        }
        
        # Step 1: 检查是否需要分子查询
        if include_molecule_context and self.molecule_agent.should_query(question):
            print("\n[Step 1] 检测到分子相关查询，执行分子性质检索...")
            
            mol_context, mol_results = self.molecule_agent.process_query(question)
            result["molecule_context"] = mol_context
            result["molecule_results"] = [
                self._serialize_mol_result(r) for r in mol_results
            ]
            
            if mol_results:
                print(f"  ✓ 找到 {len(mol_results)} 个相关分子")
                for r in mol_results:
                    if r.query_success:
                        print(f"    • {r.molecule.identifier}: {r.molecule.molecular_formula or 'N/A'}")
        else:
            print("\n[Step 1] 未检测到分子相关查询，跳过分子检索")
        
        # Step 2: 文档检索 (这里是占位，实际使用时调用你的 RAG 系统)
        print("\n[Step 2] 执行文档向量检索...")
        # doc_context = self.doc_retrieval_agent.retrieve(question, top_k)
        result["doc_context"] = "[文档检索结果占位]"
        
        # Step 3: 图谱检索 (这里是占位，实际使用时调用你的 Graph RAG)
        print("\n[Step 3] 执行知识图谱检索...")
        # graph_context = self.graph_retrieval_agent.retrieve(question)
        result["graph_context"] = "[图谱检索结果占位]"
        
        # Step 4: 信息融合
        print("\n[Step 4] 融合多源信息...")
        combined_context = self._fuse_contexts(
            result["molecule_context"],
            result["doc_context"],
            result["graph_context"]
        )
        
        # Step 5: 生成回答 (这里是占位，实际使用时调用你的 LLM)
        print("\n[Step 5] 生成回答...")
        if self.llm:
            prompt = self._build_answer_prompt(question, combined_context)
            result["answer"] = self.llm.call_llm(prompt)
        else:
            result["answer"] = f"[LLM未初始化]\n\n融合上下文:\n{combined_context}"
        
        # 输出结果
        print(f"\n{'='*80}")
        print("【答案】")
        print('='*80)
        print(result["answer"][:500] + "..." if len(result["answer"]) > 500 else result["answer"])
        print('='*80)
        
        return result
    
    def _fuse_contexts(self, 
                       molecule_context: str, 
                       doc_context: str, 
                       graph_context: str) -> str:
        """融合多源上下文"""
        parts = []
        
        if molecule_context:
            parts.append("【分子性质数据】\n" + molecule_context)
        
        if doc_context and doc_context != "[文档检索结果占位]":
            parts.append("【文档检索结果】\n" + doc_context)
        
        if graph_context and graph_context != "[图谱检索结果占位]":
            parts.append("【知识图谱结果】\n" + graph_context)
        
        return "\n\n".join(parts)
    
    def _build_answer_prompt(self, question: str, context: str) -> str:
        """构建回答生成的 Prompt"""
        return f"""基于以下信息回答用户的问题。

参考信息:
{context}

用户问题: {question}

请提供准确、专业的回答。如果信息中包含分子性质数据，请适当引用这些数据来支持你的回答。
如果某些信息不确定或缺失，请明确指出。

回答:"""
    
    def _serialize_mol_result(self, result: MoleculeQueryResult) -> Dict[str, Any]:
        """序列化分子查询结果"""
        return {
            "identifier": result.molecule.identifier,
            "smiles": result.molecule.canonical_smiles,
            "formula": result.molecule.molecular_formula,
            "is_valid": result.molecule.is_valid,
            "rfb_relevance": result.rfb_relevance,
            "properties_count": len(result.properties),
            "dataset_matches": len(result.dataset_matches),
            "success": result.query_success,
            "errors": result.errors
        }
    
    def query_molecule_only(self, identifier: str) -> Dict[str, Any]:
        """仅查询分子性质（不进行 RAG 检索）
        
        用于快速获取分子信息
        """
        result = self.molecule_tool.query(identifier)
        
        return {
            "identifier": identifier,
            "success": result.query_success,
            "formatted": self.molecule_tool.format_result_for_context(result) if result.query_success else None,
            "raw": self._serialize_mol_result(result),
            "errors": result.errors
        }
    
    def list_known_molecules(self, category: str = None) -> List[Dict[str, Any]]:
        """列出已知的液流电池相关分子
        
        Args:
            category: 分子类别 ("anolyte", "catholyte", "electrolyte", "solvent", "additive", None=全部)
        """
        lib = self.molecule_tool.rfb_library
        molecules = []
        
        category_map = {
            "anolyte": lib.anolyte_molecules,
            "catholyte": lib.catholyte_molecules,
            "electrolyte": lib.supporting_electrolytes,
            "solvent": lib.solvents,
            "additive": lib.additives
        }
        
        if category and category in category_map:
            for mol_id, mol_data in category_map[category].items():
                molecules.append({
                    "id": mol_id,
                    "names": mol_data.get("names", []),
                    "category": category,
                    "smiles": mol_data.get("smiles"),
                    "redox_potential": mol_data.get("redox_potential")
                })
        else:
            # 返回全部
            for cat_name, cat_dict in category_map.items():
                for mol_id, mol_data in cat_dict.items():
                    molecules.append({
                        "id": mol_id,
                        "names": mol_data.get("names", []),
                        "category": cat_name,
                        "smiles": mol_data.get("smiles"),
                        "redox_potential": mol_data.get("redox_potential")
                    })
        
        return molecules


# ============================================================================
# 与现有 part1_integration.py 的集成方法
# ============================================================================

def patch_integrated_qa_system(original_system, enable_deepchem: bool = True):
    """
    给现有的 IntegratedQASystem 打补丁，添加分子查询功能
    
    使用方法:
        from part1_integration import IntegratedQASystem
        from molecule_integration import patch_integrated_qa_system
        
        system = IntegratedQASystem()
        patch_integrated_qa_system(system)
        
        # 现在 system 有了分子查询能力
        result = system.query_with_molecules("DHPS的溶解度是多少？")
    """
    
    # 初始化分子工具
    molecule_tool = MoleculePropertyTool(enable_deepchem=enable_deepchem)
    molecule_agent = MoleculeQueryAgent(enable_deepchem=enable_deepchem)
    
    # 如果系统有 LLM，连接到 molecule_agent
    if hasattr(original_system, 'arsenal') and original_system.arsenal:
        llm = original_system.arsenal.get_llm()
        molecule_agent.llm = llm
    
    # 附加到原系统
    original_system.molecule_tool = molecule_tool
    original_system.molecule_agent = molecule_agent
    
    # 添加增强查询方法
    def query_with_molecules(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """增强查询 - 包含分子性质"""
        
        # 检查是否需要分子查询
        mol_context = ""
        mol_results = []
        
        if self.molecule_agent.should_query(question):
            mol_context, mol_results = self.molecule_agent.process_query(question)
        
        # 调用原始查询
        original_result = self._query_with_agents(question, top_k)
        
        # 如果有分子上下文，重新生成答案
        if mol_context:
            # 融合上下文并重新生成
            enhanced_context = f"""
【分子性质数据】
{mol_context}

【原始检索结果】
{original_result.get('answer', '')}
"""
            # 可以选择是否重新调用 LLM
            original_result['molecule_context'] = mol_context
            original_result['molecule_results'] = [
                {
                    "identifier": r.molecule.identifier,
                    "formula": r.molecule.molecular_formula,
                    "rfb_role": r.rfb_relevance.get("role")
                }
                for r in mol_results if r.query_success
            ]
        
        return original_result
    
    # 绑定方法
    import types
    original_system.query_with_molecules = types.MethodType(query_with_molecules, original_system)
    
    logger.info("✓ 分子查询功能已添加到 IntegratedQASystem")
    return original_system


# ============================================================================
# 演示
# ============================================================================

def demo():
    """演示增强版问答系统"""
    
    print("\n" + "="*80)
    print("🔬 增强版问答系统演示 (RAG + 分子性质查询)")
    print("="*80 + "\n")
    
    # 初始化系统（不启用 DeepChem 以加快测试）
    system = EnhancedIntegratedQASystem(enable_deepchem=False)
    
    # 测试查询
    test_questions = [
        "DHPS的溶解度和氧化还原电位是多少？",
        "TEMPO作为正极材料有什么特点？",
        "蒽醌类分子在液流电池中的应用",
        "吩嗪和醌类哪个更适合做负极材料？",
        "液流电池的工作原理是什么？",  # 不涉及具体分子
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n\n{'#'*80}")
        print(f"# 测试 {i}")
        print(f"{'#'*80}")
        
        result = system.query(question)
        
        # 打印分子查询结果
        if result.get("molecule_results"):
            print(f"\n📊 检测到的分子: {[r['identifier'] for r in result['molecule_results']]}")
    
    # 测试单独的分子查询
    print("\n\n" + "="*80)
    print("📋 单独分子查询测试")
    print("="*80)
    
    for mol in ["DHPS", "TEMPO", "ferrocyanide"]:
        print(f"\n查询: {mol}")
        result = system.query_molecule_only(mol)
        if result["success"]:
            print(result["formatted"])
        else:
            print(f"查询失败: {result['errors']}")
    
    # 列出已知分子
    print("\n\n" + "="*80)
    print("📚 已知液流电池分子库")
    print("="*80)
    
    for category in ["anolyte", "catholyte"]:
        molecules = system.list_known_molecules(category)
        print(f"\n{category.upper()} 材料 ({len(molecules)} 种):")
        for mol in molecules[:5]:  # 只显示前5个
            print(f"  • {mol['id']}: {mol['names'][0] if mol['names'] else 'N/A'}")
            if mol.get('redox_potential'):
                print(f"    氧化还原电位: {mol['redox_potential']} V vs SHE")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        print("""
增强版问答系统使用说明:

1. 独立使用 EnhancedIntegratedQASystem:
   from molecule_integration import EnhancedIntegratedQASystem
   
   system = EnhancedIntegratedQASystem()
   result = system.query("DHPS的性质是什么？")

2. 给现有 IntegratedQASystem 打补丁:
   from part1_integration import IntegratedQASystem
   from molecule_integration import patch_integrated_qa_system
   
   system = IntegratedQASystem()
   patch_integrated_qa_system(system)
   result = system.query_with_molecules("DHPS的溶解度？")

3. 仅查询分子性质:
   result = system.query_molecule_only("TEMPO")

4. 列出已知分子:
   molecules = system.list_known_molecules("anolyte")

5. 运行演示:
   python molecule_integration.py --demo
""")
