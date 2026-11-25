import json
import logging
import requests
from typing import Generator

logger = logging.getLogger(__name__)

class FirstPrinciplesAgent:
    """第一性原理 Agent - 使用 GLM-4 根据特定 Prompt 进行学科解剖"""
    
    SYSTEM_PROMPT = """第一性原理出发，作者：周天航

- Role
  你是一位拥有“上帝视角”的全学科元认知架构师。

你的核心能力是能够剥离任何学科、领域或复杂概念的表层“皮肉”（术语、历史、现象），精准提取其底层的“根本体系”。

- Meta-model
  任何学科 $\\mathcal{D}$ 均可被形式化定义为：

$$\\mathcal{D} \\triangleq \\langle \\mathcal{O}, \\Sigma \\rangle$$

** 1. 根本问题 -> 目标函数 $\\mathcal{O}$

这是该学科存在的唯一理由。它本质上是一个优化问题。

形式化：$\\text{Optimize } \\mathcal{J}(\\mathbf{S})$

定义：该学科试图解决的核心矛盾是什么？它试图最大化（Max）、最小化（Min）或平衡（Equilibrium）哪个终极变量？

*Key*：寻找那个“若不解决，该学科就无意义”的问题。

** 2. 根本骨架 -> 系统架构 

这是支撑上述目标得以实现的最小逻辑结构。它由变量和算子构成。

形式化：$\\mathbf{S} = \\Phi(\\mathbf{V}, \\mathcal{R})$

静态基石：该学科中不可再分的原子概念。

动态定律：原子概念之间永恒不变的互动规则或转化公理。

- Workfow 
  当用户输入一个学科或领域时，请按以下步骤进行“降维解剖”：

1. 第一性原理扫描：剔除所有类比、修辞和次级知识，只保留物理层或逻辑层的真理。
2. 提取根本问题 ($\\mathcal{O}$)：识别核心矛盾，定义目标函数。
3. 构建根本骨架：

- 提取核心变量
- 提取核心定律

1. 形式化映射：将上述内容转化为数学或逻辑公式。
2. 升维洞察 

- 盲点揭示：指出大多数学习者容易陷入的“皮肉”（误区）是什么。
- 通关秘籍：基于骨架，给出掌握该学科的最高效路径。
- 精炼总结：该学科本质上就是用 [核心骨架] 去求解 [根本问题]。

1. 升维图谱

- 输出该学科领域的「真正问」和「根本体系」"""

    def __init__(self, llm_config):
        """
        Args:
            llm_config: 包含 api_key, base_url, model 等配置的对象
        """
        self.llm_config = llm_config
        # 【切换】原 SiliconFlow key 全部欠费, 切到 Moonshot Kimi K2.6 (thinking 模型)
        self.api_key = __import__("os").environ.get("MOONSHOT_API_KEY", "")
        self.base_url = "https://api.moonshot.cn/v1"
        self.model = "kimi-k2.6"
        
        self.name = "FirstPrinciplesAgent"

    def generate_stream(self, question: str) -> Generator[str, None, None]:
        """流式生成第一性原理回答"""
        # 优先使用本地设置
        base_url = getattr(self, 'base_url', self.llm_config.base_url)
        api_url = f"{base_url.rstrip('/')}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 优先使用本地设置
        model = getattr(self, 'model', self.llm_config.model)
        
        # 【补丁】kimi-k2.x thinking 系列必须 temperature=1.0, 否则 content 会全空
        _temp = 1.0 if isinstance(model, str) and model.startswith("kimi-k2.") else 0.2
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            "temperature": _temp,
            "stream": True
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=data, stream=True, timeout=60)
            if response.status_code != 200:
                yield f"❌ GLM调用失败 ({response.status_code}): {response.text}"
                return

            reasoning_started = False
            for line in response.iter_lines():
                if not line:
                    continue
                
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    line_str = line_str[6:]
                
                if line_str == '[DONE]':
                    break
                
                try:
                    chunk = json.loads(line_str)
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        delta = chunk['choices'][0].get('delta', {})
                        
                        # 【新增】处理思考过程 (Reasoning Content)
                        reasoning = delta.get('reasoning_content', '')
                        if reasoning:
                            if not reasoning_started:
                                print("\n" + ">" * 30 + " [FP Agent 思考中] " + ">" * 30 + "\n", end='', flush=True)
                                reasoning_started = True
                            yield {"type": "reasoning", "content": reasoning}
                            
                        # 提取正式回答内容
                        content = delta.get('content', '')
                        if content:
                            if reasoning_started:
                                print("\n" + "<" * 30 + " [思考结束] " + "<" * 30 + "\n", end='', flush=True)
                                reasoning_started = False
                            yield {"type": "content", "content": content}
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            yield f"❌ 第一性原理生成异常: {str(e)}"
