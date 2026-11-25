import os
# 测试拼接路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
print(project_root)
save_dir = os.path.join(project_root, "src","graphrag_and_rag" ,"graph_rag", "llm_responses")

print(save_dir)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(PROJECT_ROOT)

merged_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
print(f"merged_data_dir: {merged_data_dir}")
