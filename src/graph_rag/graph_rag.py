"""
GraphRAG系统实现

该模块实现了GraphRAG功能，专门处理需要全局推理和跨文档理解的复杂问题。
GraphRAG通过构建知识图谱来理解文档间的关系，从而回答复杂的全局性问题。
"""

import os
import json
from typing import List, Dict, Set
import re
from neo4j import GraphDatabase, basic_auth

class GraphRAG:
    """
    GraphRAG系统
    
    该系统专门处理需要全局推理的问题，通过以下方式工作：
    1. 构建文档（或段落）间的知识图谱
    2. 理解文档（或段落）间的关系和连接
    3. 回答涉及多个文档（或段落）的复杂问题
    """
    
    def __init__(self, data_directory: str):
        """
        初始化GraphRAG系统
        
        Args:
            data_directory: 转换后的MD文件所在目录（通常是 pdf_to_md/extraction_results）
        """
        # 转换为绝对路径，确保相对路径正确解析
        if not os.path.isabs(data_directory):
            # 如果是相对路径，基于项目根目录来解析
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_directory = os.path.join(project_root, data_directory)
        self.data_directory = data_directory
        
        # 确定MD文件的实际位置
        # 优先检查 pdf_to_md/extraction_results/downloaded_files
        # 从 src/graph_rag 向上3级到项目根目录，再进入 pdf_to_md/extraction_results/downloaded_files
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pdf_to_md_path = os.path.join(project_root, "pdf_to_md", "extraction_results", "downloaded_files")
        if os.path.exists(pdf_to_md_path):
            self.md_files_directory = pdf_to_md_path
        else:
            # 备选：data_directory/downloaded_files
            self.md_files_directory = os.path.join(self.data_directory, "downloaded_files")
        # self.documents 现在存储的是段落，键是 "文档ID_段落索引"
        self.documents = {}  
        
        # 步骤一（加载与解析 Markdown 文件）
        self._load_and_parse_documents()
        
        # 步骤二（（实体抽取和关系抽取））
        # 加载Prompt模板（必须在构建图谱之前调用）
        # 实体抽取
        self.prompt_templates = self._load_prompt_templates()
        # 关系抽取
        self.prompt_templates_relation = self._load_prompt_templates_relation()
        self.paragraph_categories = {}  # 保持兼容性，但不再使用

        # 初始化图谱相关变量
        self.graph = {"nodes": {}, "edges": {}}
        self.node_counter = 0
        self.edge_counter = 0

        # Neo4j 连接配置（根据你的实际情况修改）
        self.neo4j_uri = "bolt://localhost:7687"  # 本地 Neo4j 默认端口
        self.neo4j_user = "neo4j"
        self.neo4j_password = __import__("os").environ.get("NEO4J_PASSWORD", "")  # 替换为你的 Neo4j 密码

        # 步骤三（构建知识图谱）：调用修复后的方法（仅一次定义）
        # 只有在有文档的情况下才构建知识图谱
        if self.documents:
            self._build_knowledge_graph()
        else:
            print("警告：未加载到任何文档，跳过知识图谱构建步骤。")

    # 步骤一（加载与解析 Markdown 文件）
    def _load_and_parse_documents(self):
        """
        加载所有转换后的MD文档。
        每个MD文件作为一个整体发送给大模型进行三元组抽取。
        """
        print("正在加载MD文档...")
        
        # 使用已确定的MD文件目录
        downloaded_files_path = self.md_files_directory
        if not os.path.exists(downloaded_files_path):
            print(f"❌ 警告: 目录 {downloaded_files_path} 不存在")
            print(f"   期望路径: {downloaded_files_path}")
            return
        
        # 遍历所有子目录
        try:
            folder_list = os.listdir(downloaded_files_path)
            print(f"📁 在目录中找到 {len(folder_list)} 个项目")
        except Exception as e:
            print(f"❌ 无法读取目录: {e}")
            return
        
        for folder_name in folder_list:
            folder_path = os.path.join(downloaded_files_path, folder_name)
            if os.path.isdir(folder_path):
                # 查找full.md文件
                md_file_path = os.path.join(folder_path, "full.md")
                if os.path.exists(md_file_path):
                    try:
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 直接使用完整内容，不再按段落分割
                        if content and len(content) > 100:
                            # 使用folder_name作为文档ID
                            doc_id = folder_name
                            self.documents[doc_id] = content
                            print(f"✅ 已加载文档 '{folder_name}'，内容长度: {len(content)} 字符")
                        else:
                            print(f"⚠️  文档 '{folder_name}' 内容为空或过短")

                    except Exception as e:
                        print(f"❌ 加载文档 {folder_name} 时出错: {e}")

        
    # 步骤二（实体抽取和关系抽取）
    # 实体抽取
    def _load_prompt_templates(self) -> Dict[str, str]:
        """
        储能材料领域知识图谱实体提取提示词。
        覆盖锂/钠/锌离子电池、液流电池、超级电容器、相变储能材料等方向。
        """
        EXTRACTION_PROMPT_TEMPLATE = """你是储能材料领域知识图谱提取专家。请从学术文献中提取所有实体。文献涵盖锂/钠/锌离子电池、液流电池、超级电容器、相变储能材料等方向。

# 实体类型（12种）

| 类型 | 说明 | 包含范围 | 示例 |
|------|------|----------|------|
| Material | 材料、化合物、电极材料、电解液、膜、相变材料 | 活性物质、基底材料、掺杂材料、合成原料、对比材料 | LiCoO₂, 高熵钙钛矿氧化物, Nafion, 月桂酸-石蜡共晶, 石墨毡 |
| Species | 离子、自由基、氧化还原态、缺陷态 | 阳离子、阴离子、氧化态、还原态、电子、质子 | Li⁺, Na⁺, Fe²⁺, Cu⁺/Cu²⁺, e⁻, H⁺ |
| Property | 性能指标(不含数值)，必须具体到材料+条件 | 比容量、效率、电导率、扩散系数、相变潜热、稳定性等 | Cu₀.₁样品比容量(200mA/g), 库伦效率(250圈), 月桂酸-石蜡相变潜热 |
| Value | 数值+单位，必须完整 | 容量、百分比、电压、电流密度、温度等 | 1174.3 mAh·g⁻¹, 99.8%, 0.084 S·cm⁻¹, 41.2 kJ/mol |
| Condition | 实验/操作条件 | 电流密度、温度、循环次数、电压范围、扫描速率 | 200 mA·g⁻¹, 25°C, 250次循环, 0.01~3.0 V |
| Reaction | 电化学/化学/热反应 | 氧化还原反应、嵌入/脱嵌反应、合成反应、固液相变 | Li⁺嵌入/脱嵌反应, 固相燃烧合成, Cr³⁺/Cr²⁺氧化还原, 固-液相变 |
| Mechanism | 反应机理、性能机理 | 离子传输机理、容量衰减机理、空位诱导机理、储热机理 | 赝电容储锂机理, 阳离子空位电荷补偿机理, 相变储热机理 |
| Component | 电池/储能系统组件 | 正极、负极、电解液、隔膜、集流体、正极液、负极液 | 负极片, Celgard隔膜, LiPF₆电解液, 铜箔集流体, 正极电解液 |
| Method | 表征/计算/合成方法 | 电化学测试、光谱分析、热分析、计算方法、合成方法 | XRD, SEM, XPS, CV, GITT, DFT计算, 溶液燃烧法, DSC测试 |
| Device | 电池/储能装置/测试系统 | 各类电池、超级电容器、储热装置、测试设备 | CR2025扣式电池, 锂离子电池, 液流电池, 相变储能装置, 三电极体系 |
| FunctionalGroup | 官能团/结构缺陷/修饰基团 | 影响性能的官能团、晶格缺陷、空位、特殊结构 | 羟基, 磺酸基, Cu阳离子空位, 氧空位, 介孔结构 |
| Catalyst | 催化剂/添加剂（明确用于催化或改性） | 必须是明确作为催化/添加用途 | Bi³⁺催化剂, 导电炭黑, 成核剂 |

---

# ID命名规则

| 类型 | ID前缀 | 示例 |
|------|--------|------|
| Material | m | m1, m2, m3 |
| Species | sp | sp1, sp2, sp3 |
| Property | p | p1, p2, p3 |
| Value | v | v1, v2, v3 |
| Condition | c | c1, c2, c3 |
| Reaction | r | r1, r2, r3 |
| Mechanism | mech | mech1, mech2 |
| Component | comp | comp1, comp2 |
| Method | met | met1, met2 |
| Device | d | d1, d2 |
| FunctionalGroup | fg | fg1, fg2 |
| Catalyst | cat | cat1, cat2 |

# 提取规则

## 规则1: Property必须独立命名
同一性能在不同材料/条件下必须创建独立Property节点，名称要具体：

✅ 正确:
  {"id":"p1", "type":"Property", "name":"Cu₀.₁样品比容量(200mA/g,250圈)"}
  {"id":"p2", "type":"Property", "name":"Cu₀.₂样品比容量(200mA/g,250圈)"}
  {"id":"p3", "type":"Property", "name":"月桂酸-石蜡共晶相变潜热"}

❌ 错误（太笼统）:
  {"id":"p1", "type":"Property", "name":"比容量"}

## 规则2: Value必须包含单位
  {"id":"v1", "type":"Value", "name":"1174.3 mAh·g⁻¹"}
  {"id":"v2", "type":"Value", "name":"41.2%"}
  {"id":"v3", "type":"Value", "name":"6.3×10⁻¹⁰ cm²·s⁻¹"}

## 规则3: Reaction可包含方程式
  {"id":"r1", "type":"Reaction", "name":"Li⁺嵌入反应", "equation":"xLi⁺ + xe⁻ + MO ⇌ LiₓMO"}

## 规则4: 区分Material、Species、FunctionalGroup
- Material: 具体材料/化合物（高熵氧化物, LiCoO₂, 月桂酸, FeCl₂）
- Species: 离子态/氧化还原态（Li⁺, Cu⁺, Cu²⁺, Fe²⁺, e⁻）
- FunctionalGroup: 官能团或结构缺陷（氧空位, 阳离子空位, 羟基, 磺酸基）

## 规则5: type字段必须是12种类型之一
❌ 错误: {"type":"XRD表征"}
✅ 正确: {"type":"Method", "name":"XRD表征"}

# 储能文献必提实体清单

□ 电极材料/活性物质（Material）
□ 母体材料及其衍生/掺杂物（Material）
□ 离子态/价态（Species）：Li⁺, Na⁺, Fe²⁺/³⁺, Cu⁺/²⁺, e⁻, H⁺
□ 官能团/结构缺陷（FunctionalGroup）：空位、官能团、特殊结构
□ 催化剂/导电添加剂（Catalyst）
□ 比容量、效率、电导率、扩散系数、相变潜热等性能（Property）
□ 所有数值数据（Value）
□ 电流密度、温度、循环次数、电压范围等条件（Condition）
□ 电化学反应/相变过程（Reaction）
□ 电池组件：正极、负极、电解液、隔膜（Component）
□ 电池/储能装置（Device）
□ 表征与合成方法：XRD、SEM、XPS、DSC、DFT、溶液燃烧法等（Method）

# 输出格式

仅输出纯JSON，格式如下：
{"entities":[{"id":"m1","type":"Material","name":"高熵钙钛矿氧化物"},{"id":"p1","type":"Property","name":"Cu₀.₁比容量(200mA/g)"}]}

# 完整示例

**输入片段：**
"采用溶液燃烧法合成高熵钙钛矿氧化物La(Cr₀.₂Fe₀.₂Mn₀.₂Ni₀.₂Cu₀.₁)O₃₋δ负极材料。在200 mA·g⁻¹电流密度下循环250圈后比容量达1174.3 mAh·g⁻¹，库伦效率接近100%。在3000 mA·g⁻¹高倍率下仍保持200.1 mAh·g⁻¹，倍率性能为Cu₀.₂样品的4倍。XPS表征确认Cu以Cu⁺/Cu²⁺共存，阳离子空位诱导氧空位（Ov占比41.2%），Li⁺扩散系数达6.3×10⁻¹⁰ cm²·s⁻¹，电导率0.084 S·cm⁻¹。"

**输出：**
{"entities":[{"id":"m1","type":"Material","name":"La(Cr₀.₂Fe₀.₂Mn₀.₂Ni₀.₂Cu₀.₁)O₃₋δ"},{"id":"m2","type":"Material","name":"Cu₀.₂样品"},{"id":"sp1","type":"Species","name":"Cu⁺"},{"id":"sp2","type":"Species","name":"Cu²⁺"},{"id":"sp3","type":"Species","name":"Li⁺"},{"id":"sp4","type":"Species","name":"e⁻"},{"id":"fg1","type":"FunctionalGroup","name":"Cu阳离子空位"},{"id":"fg2","type":"FunctionalGroup","name":"氧空位"},{"id":"r1","type":"Reaction","name":"Li⁺嵌入/脱嵌反应","equation":"xLi⁺ + xe⁻ + MO ⇌ LiₓMO"},{"id":"mech1","type":"Mechanism","name":"阳离子空位电荷补偿机理"},{"id":"p1","type":"Property","name":"Cu₀.₁比容量(200mA/g,250圈)"},{"id":"p2","type":"Property","name":"Cu₀.₁比容量(3000mA/g)"},{"id":"p3","type":"Property","name":"库伦效率"},{"id":"p4","type":"Property","name":"倍率性能(vs Cu₀.₂)"},{"id":"p5","type":"Property","name":"氧空位浓度"},{"id":"p6","type":"Property","name":"Li⁺扩散系数"},{"id":"p7","type":"Property","name":"电导率"},{"id":"v1","type":"Value","name":"1174.3 mAh·g⁻¹"},{"id":"v2","type":"Value","name":"200.1 mAh·g⁻¹"},{"id":"v3","type":"Value","name":"100%"},{"id":"v4","type":"Value","name":"4倍"},{"id":"v5","type":"Value","name":"41.2%"},{"id":"v6","type":"Value","name":"6.3×10⁻¹⁰ cm²·s⁻¹"},{"id":"v7","type":"Value","name":"0.084 S·cm⁻¹"},{"id":"c1","type":"Condition","name":"200 mA·g⁻¹"},{"id":"c2","type":"Condition","name":"250次循环"},{"id":"c3","type":"Condition","name":"3000 mA·g⁻¹"},{"id":"comp1","type":"Component","name":"负极"},{"id":"met1","type":"Method","name":"溶液燃烧法"},{"id":"met2","type":"Method","name":"XPS表征"},{"id":"d1","type":"Device","name":"CR2025扣式半电池"}]}

# 常见错误避免

1. ❌ type写成具体内容，如 type:"XRD" → ✅ type:"Method", name:"XRD表征"
2. ❌ Property太笼统，如 name:"比容量" → ✅ name:"Cu₀.₁比容量(200mA/g,250圈)"
3. ❌ Value没有单位，如 name:"1174.3" → ✅ name:"1174.3 mAh·g⁻¹"
4. ❌ 混淆Material和Species，Li⁺是Species不是Material
5. ❌ 遗漏母体/对比材料
6. ❌ 遗漏e⁻和Li⁺/Na⁺等参与反应的Species

# 文献内容

{markdown_content}

# 输出要求

1. 仅输出纯JSON，不要包含任何其他文字、解释、Markdown或代码块
2. 所有字符串必须用双引号包围
3. 禁止换行符出现在字符串内部，用空格代替
4. 确保JSON结构完整，以 } 结尾
5. 目标：提取100个实体以上
6. 如果内容太多，优先保证JSON语法正确，可截断部分内容但不要破坏结构

"""
        return {"UNIFIED": EXTRACTION_PROMPT_TEMPLATE}


    # 关系抽取
    def _load_prompt_templates_relation(self) -> Dict[str, str]:
        """
        储能材料领域知识图谱关系提取提示词。
        """
        EXTRACTION_PROMPT_TEMPLATE = """你是储能材料领域知识图谱提取专家。请基于已提取的实体，提取它们之间的关系。文献涵盖锂/钠/锌离子电池、液流电池、超级电容器、相变储能材料等方向。

# 已提取实体

{entities_json}

# 关系类型（22种）

【性能关系】
- HAS_PROPERTY → (Material/Device, HAS_PROPERTY, Property) 材料/装置具有某性能
- HAS_VALUE → (Property, HAS_VALUE, Value) 性能的具体数值
- MEASURED_AT → (Property, MEASURED_AT, Condition) 测量条件

【结构关系】
- DERIVED_FROM → (Material, DERIVED_FROM, Material) 衍生物/掺杂物来源于母体
- HAS_FUNCTIONAL_GROUP → (Material, HAS_FUNCTIONAL_GROUP, FunctionalGroup) 材料含有官能团或缺陷
- CONTAINS → (Device/Component, CONTAINS, Component/Material) 装置包含组件
- USED_AS → (Material, USED_AS, Component) 材料用作某组件
- PAIRED_WITH → (Material, PAIRED_WITH, Material) 正负极材料配对

【合成/制备关系】
- SYNTHESIZED_FROM → (Material, SYNTHESIZED_FROM, Material) 从前体合成
- PRODUCT → (Reaction, PRODUCT, Material/Species) 反应产物
- SYNTHESIS_YIELD → (Reaction, SYNTHESIS_YIELD, Value) 合成产率
- MODIFIED_BY → (Material, MODIFIED_BY, Method) 材料被某方法改性

【因果关系】
- IMPROVES → (任意, IMPROVES, Property) 提高某性能
- REDUCES → (任意, REDUCES, Property) 降低某性能
- CAUSES → (任意, CAUSES, Property/现象) 导致某现象
- PREVENTS → (任意, PREVENTS, Property/问题) 抑制某问题
- ENABLES → (任意, ENABLES, 能力/性质) 使某事成为可能

【反应机理关系】
- REACTANT → (Reaction, REACTANT, Species/Material) 反应物
- INVOLVES → (Reaction, INVOLVES, Species) 涉及的电子/质子/离子
- CATALYZED_BY → (Reaction, CATALYZED_BY, Catalyst) 被催化剂催化
- OCCURS_AT → (Reaction, OCCURS_AT, Component) 反应发生位置

【表征关系】
- CHARACTERIZED_BY → (Material/Property, CHARACTERIZED_BY, Method) 被某方法表征

# 关系提取规则

## 规则1: 性能数据链必须完整
Material → Property → Value → Condition 形成完整链路：

示例：Cu₀.₁样品在200 mA/g下循环250圈比容量1174.3 mAh/g
  (m1, HAS_PROPERTY, p1)   // 材料 → 比容量
  (p1, HAS_VALUE, v1)       // 比容量 → 1174.3 mAh·g⁻¹
  (p1, MEASURED_AT, c1)     // 比容量 → 200 mA·g⁻¹条件

## 规则2: 衍生物/掺杂关系
文献中提到"X的衍生物"、"基于X"、"X掺杂"、"X derivatives"时：
  (衍生物/掺杂物, DERIVED_FROM, 母体)

示例：La(Cr₀.₂Fe₀.₂Mn₀.₂Ni₀.₂Cu₀.₁)O₃₋δ基于LaCrO₃结构
  (m1, DERIVED_FROM, m_base)

## 规则3: 反应机理必须完整
每个Reaction应该连接其REACTANT、PRODUCT、INVOLVES：

示例：Li⁺嵌入反应
  (r1, REACTANT, sp1)   // 反应 → Li⁺
  (r1, INVOLVES, sp4)   // 反应 → e⁻
  (r1, OCCURS_AT, comp1) // 反应 → 负极

## 规则4: 因果关系必须提取
识别文献中的因果表述：
- "X提高了Y" / "X enhances Y" → (X, IMPROVES, Y)
- "X降低了Y" / "X reduces Y" → (X, REDUCES, Y)
- "X导致Y" / "X causes Y" → (X, CAUSES, Y)
- "X抑制了Y" / "X prevents Y" → (X, PREVENTS, Y)
- "引入X后，Y提升" → (X, IMPROVES, Y)

示例：Cu阳离子空位诱导氧空位，降低Li⁺扩散能垒
  (fg1, CAUSES, fg2)    // 阳离子空位 → 氧空位
  (fg2, IMPROVES, p6)   // 氧空位 → Li⁺扩散系数

## 规则5: 装置结构关系
  (Device, CONTAINS, Component)
  (Material, USED_AS, Component)

示例：扣式半电池包含负极，负极材料为高熵氧化物
  (d1, CONTAINS, comp1)   // 电池 → 负极
  (m1, USED_AS, comp1)    // 材料 → 负极

## 规则6: source和target必须是已提取实体的id
关系的source和target只能使用上面"已提取实体"中存在的id，不能创造新id。

# 输出格式

仅输出纯JSON，格式如下：
{"relations":[{"source":"m1","relation":"HAS_PROPERTY","target":"p1"},{"source":"p1","relation":"HAS_VALUE","target":"v1"}]}

# 完整示例

**已提取实体：**
{"entities":[{"id":"m1","type":"Material","name":"La(Cr₀.₂Fe₀.₂Mn₀.₂Ni₀.₂Cu₀.₁)O₃₋δ"},{"id":"m2","type":"Material","name":"Cu₀.₂样品"},{"id":"sp1","type":"Species","name":"Li⁺"},{"id":"sp2","type":"Species","name":"e⁻"},{"id":"sp3","type":"Species","name":"Cu⁺"},{"id":"sp4","type":"Species","name":"Cu²⁺"},{"id":"fg1","type":"FunctionalGroup","name":"Cu阳离子空位"},{"id":"fg2","type":"FunctionalGroup","name":"氧空位"},{"id":"r1","type":"Reaction","name":"Li⁺嵌入/脱嵌反应"},{"id":"mech1","type":"Mechanism","name":"阳离子空位电荷补偿机理"},{"id":"p1","type":"Property","name":"Cu₀.₁比容量(200mA/g,250圈)"},{"id":"p2","type":"Property","name":"Cu₀.₁比容量(3000mA/g)"},{"id":"p3","type":"Property","name":"库伦效率"},{"id":"p4","type":"Property","name":"倍率性能(vs Cu₀.₂)"},{"id":"p5","type":"Property","name":"Li⁺扩散系数"},{"id":"p6","type":"Property","name":"电导率"},{"id":"v1","type":"Value","name":"1174.3 mAh·g⁻¹"},{"id":"v2","type":"Value","name":"200.1 mAh·g⁻¹"},{"id":"v3","type":"Value","name":"100%"},{"id":"v4","type":"Value","name":"4倍"},{"id":"v5","type":"Value","name":"6.3×10⁻¹⁰ cm²·s⁻¹"},{"id":"v6","type":"Value","name":"0.084 S·cm⁻¹"},{"id":"c1","type":"Condition","name":"200 mA·g⁻¹"},{"id":"c2","type":"Condition","name":"250次循环"},{"id":"c3","type":"Condition","name":"3000 mA·g⁻¹"},{"id":"comp1","type":"Component","name":"负极"},{"id":"met1","type":"Method","name":"溶液燃烧法"},{"id":"met2","type":"Method","name":"XPS表征"},{"id":"d1","type":"Device","name":"CR2025扣式半电池"}]}

**输出：**
{"relations":[{"source":"m1","relation":"USED_AS","target":"comp1"},{"source":"d1","relation":"CONTAINS","target":"comp1"},{"source":"m1","relation":"HAS_FUNCTIONAL_GROUP","target":"fg1"},{"source":"m1","relation":"HAS_FUNCTIONAL_GROUP","target":"fg2"},{"source":"fg1","relation":"CAUSES","target":"fg2"},{"source":"fg2","relation":"IMPROVES","target":"p5"},{"source":"fg2","relation":"IMPROVES","target":"p6"},{"source":"m1","relation":"HAS_PROPERTY","target":"p1"},{"source":"p1","relation":"HAS_VALUE","target":"v1"},{"source":"p1","relation":"MEASURED_AT","target":"c1"},{"source":"p1","relation":"MEASURED_AT","target":"c2"},{"source":"m1","relation":"HAS_PROPERTY","target":"p2"},{"source":"p2","relation":"HAS_VALUE","target":"v2"},{"source":"p2","relation":"MEASURED_AT","target":"c3"},{"source":"m1","relation":"HAS_PROPERTY","target":"p3"},{"source":"p3","relation":"HAS_VALUE","target":"v3"},{"source":"m1","relation":"HAS_PROPERTY","target":"p4"},{"source":"p4","relation":"HAS_VALUE","target":"v4"},{"source":"m1","relation":"HAS_PROPERTY","target":"p5"},{"source":"p5","relation":"HAS_VALUE","target":"v5"},{"source":"m1","relation":"HAS_PROPERTY","target":"p6"},{"source":"p6","relation":"HAS_VALUE","target":"v6"},{"source":"r1","relation":"REACTANT","target":"sp1"},{"source":"r1","relation":"INVOLVES","target":"sp2"},{"source":"r1","relation":"OCCURS_AT","target":"comp1"},{"source":"m1","relation":"CHARACTERIZED_BY","target":"met2"},{"source":"m1","relation":"SYNTHESIZED_FROM","target":"met1"},{"source":"sp3","relation":"INVOLVES","target":"mech1"},{"source":"sp4","relation":"INVOLVES","target":"mech1"}]}

# 关系提取检查清单

□ 每个Property都连接了对应的Value（HAS_VALUE）
□ 每个Property都连接了测量条件（MEASURED_AT）如果有的话
□ 每个Material都有至少一条关系
□ 衍生物/掺杂物都连接了母体（DERIVED_FROM）
□ 官能团/缺陷都连接了对应材料（HAS_FUNCTIONAL_GROUP）
□ 反应都连接了反应物和离子（REACTANT, INVOLVES）
□ 因果关系都提取了（IMPROVES, REDUCES, CAUSES）
□ 装置结构完整（CONTAINS, USED_AS）
□ 表征方法都连接了对应材料（CHARACTERIZED_BY）

# 常见错误避免

1. ❌ source或target使用了不存在的id
2. ❌ 遗漏Property→Value的HAS_VALUE关系
3. ❌ 遗漏衍生物/掺杂物的DERIVED_FROM关系
4. ❌ 遗漏空位/官能团的HAS_FUNCTIONAL_GROUP关系
5. ❌ 遗漏因果关系IMPROVES/REDUCES/CAUSES
6. ❌ 关系方向错误，如写成 (Property, HAS_PROPERTY, Material)

# 文献内容

{markdown_content}

# 输出要求

1. 仅输出纯JSON，不要包含任何其他文字、解释、Markdown或代码块
2. 所有字符串必须用双引号包围
3. source和target必须是已提取实体中存在的id
4. 确保JSON结构完整，以 } 结尾
5. 目标：提取80-150条关系
6. 确保无孤立节点（每个实体至少有一条关系指向或来自它）
7. 如果内容太多，优先保证JSON语法正确，可截断部分内容但不要破坏结构

"""
        return {"UNIFIED": EXTRACTION_PROMPT_TEMPLATE}



    def get_prompt_for_document(self, doc_id: str) -> str:
        """
        根据文档ID返回对应的填充好内容的Prompt。
        
        Args:
            doc_id: 文档的ID。
            
        Returns:
            一个可以直接发送给LLM的完整Prompt字符串。
        """
        # 使用统一的UNIFIED模板
        template = self.prompt_templates.get("UNIFIED")
        if not template:
            print(f"错误：未找到UNIFIED模板")
            return ""
        content = self.documents.get(doc_id, "")
        
        # 将模板中的占位符 {markdown_content} 替换为实际的文档内容
        return template.replace("{markdown_content}", content)

    def get_prompt_for_relations(self, doc_id: str, entities_json: Dict) -> str:
        """
        根据文档ID和第一步提取的实体JSON，返回对应的关系提取Prompt。
        
        Args:
            doc_id: 文档的ID。
            entities_json: 第一步提取的实体JSON（dict格式）。
            
        Returns:
            一个可以直接发送给LLM的完整关系提取Prompt字符串。
        """
        # 使用统一的UNIFIED模板
        template = self.prompt_templates_relation.get("UNIFIED")
        if not template:
            print(f"错误：未找到关系提取UNIFIED模板")
            return ""
        content = self.documents.get(doc_id, "")
        
        # 将entities_json转换为JSON字符串
        entities_json_str = json.dumps(entities_json, ensure_ascii=False, indent=2)
        
        # 将模板中的占位符替换为实际的内容
        prompt = template.replace("{markdown_content}", content)
        prompt = prompt.replace("{entities_json}", entities_json_str)
        
        return prompt

    


    # 步骤三（构建知识图谱）：修复重复定义，整合所有逻辑
    def _build_knowledge_graph(self):
        """
        构建知识图谱的主方法。
        第一步：调用大模型API提取主实体，保存返回的JSON文件。
        第二步：基于提取的主实体，调用大模型API提取关系和客实体，保存返回的JSON文件。
        后续步骤（图谱构建、neo4j导入）暂不执行。
        """
        print("\n=== 开始步骤一：提取主实体 ===")
        print("注意：此过程会调用 API，可能需要较长时间和一定费用。")

        # 处理所有文本
        paragraphs_to_process = list(self.documents.items())
        
        total = len(paragraphs_to_process)
        processed_step1 = 0
        failed_step1 = 0
        
        # 存储第一步和第二步的结果
        entities_by_doc = {}  # {doc_id: entities_json}
        relations_by_doc = {}  # {doc_id: relations_json}
        
        for i, (para_id, content) in enumerate(paragraphs_to_process):
            print(f"\n【步骤一】处理进度: {i+1}/{total} (文档: {para_id[:30]}...)")
            
            # 1. 获取整个文档的 Prompt
            prompt = self.get_prompt_for_document(para_id)
            
            # 2. 调用 API 一次性抽取整个文档的主实体
            extracted_entities = self._extract_knowledge_from_paragraph_dashscope(prompt, para_id)
            
            # 3. 检查是否成功提取
            if extracted_entities:
                processed_step1 += 1
                entities_by_doc[para_id] = extracted_entities
                print(f"  【成功】 主实体提取成功")
            else:
                failed_step1 += 1
                print(f"  【失败】 未能抽取到有效信息")

        # ========== 第一步完成 ==========
        print("\n=== 步骤一完成 ===")
        print(f"主实体提取完毕。")
        print(f" - 总文档数: {total}")
        print(f" - 成功处理: {processed_step1}")
        print(f" - 处理成功率: {processed_step1/total*100:.1f}%" if total > 0 else " - 处理成功率: 0%")
        # print(f"\n大模型返回的实体JSON文件已保存至 'src/llm_responses/' 目录。")
        
        # ========== 开始步骤二：提取关系 ==========
        print("\n=== 开始步骤二：提取关系 ===")
        processed_step2 = 0
        failed_step2 = 0
        
        for i, (para_id, extracted_entities) in enumerate(entities_by_doc.items()):
            print(f"\n【步骤二】处理进度: {i+1}/{len(entities_by_doc)} (文档: {para_id[:30]}...)")
            
            # 1. 获取关系提取的Prompt
            relations_prompt = self.get_prompt_for_relations(para_id, extracted_entities)
            
            # 2. 调用API提取关系
            extracted_relations = self._extract_relations_from_paragraph_dashscope(relations_prompt, para_id)
            
            # 3. 检查是否成功提取
            if extracted_relations:
                processed_step2 += 1
                relations_by_doc[para_id] = extracted_relations  # 存储关系数据
                print(f"  【成功】 关系提取成功")
            else:
                failed_step2 += 1
                relations_by_doc[para_id] = {"relations": []}  # 保存空关系
                print(f"  【失败】 未能抽取到有效关系信息")
        
        # ========== 第二步完成 ==========
        print("\n=== 步骤二完成 ===")
        print(f"关系提取完毕。")
        print(f" - 总文档数: {len(entities_by_doc)}")
        print(f" - 成功处理: {processed_step2}")
        print(f" - 处理成功率: {processed_step2/len(entities_by_doc)*100:.1f}%" if len(entities_by_doc) > 0 else " - 处理成功率: 0%")
        # print(f"\n大模型返回的关系JSON文件已保存至 'src/llm_responses/' 目录。")
        
        # ========== 开始步骤三：合并实体和关系JSON文件 ==========
        print("\n=== 开始步骤三：合并实体和关系JSON文件 ===")
        merged_files = self._merge_entities_and_relations(entities_by_doc, relations_by_doc)
        
        # ========== 自动进入评测和改进阶段 ==========
        if merged_files:
            print("\n" + "="*60)
            print("合并完成！现在进入【自动评测和改进阶段】")
            print("="*60)
            self._perform_validation_and_reextraction(merged_files, entities_by_doc)
        
        # 禁用全局图谱优化以避免耗时操作
        # self._optimize_global_graph_connectivity()
        
        # 保存到本地 JSON（可选，仅用于调试）
        # with open('knowledge_graph.json', 'w', encoding='utf-8') as f:
        #     json.dump(self.graph, f, ensure_ascii=False, indent=4)
        # print("知识图谱已保存至 'knowledge_graph.json'。")

        # 导入到 Neo4j（暂不执行）
        # self._export_to_neo4j()


    # ... 图谱优化和构建方法已移至 build_and_import_graph.py ...

    def _parse_extraction_knowledge(self, knowledge: Dict, entities: list, relationships: list):
        """
        从新格式的提取结果中提取实体和关系。
        """
        # 1. 从文档信息提取
        document_info = knowledge.get("document_info", {})
        if isinstance(document_info, dict):
            if document_info.get("title"):
                entities.append({
                    "name": document_info["title"],
                    "type": "Paper",
                    "properties": {"source": "extraction"}
                })
            if document_info.get("authors") and isinstance(document_info["authors"], list):
                for author in document_info["authors"]:
                    if author:
                        entities.append({
                            "name": author,
                            "type": "Author",
                            "properties": {"source": "extraction"}
                        })
        
        # 2. 从物料提取
        materials = knowledge.get("materials", {})
        if isinstance(materials, dict):
            # 提取电解液
            electrolyte = materials.get("electrolyte", {})
            if isinstance(electrolyte, dict):
                if electrolyte.get("positive"):
                    entities.append({
                        "name": str(electrolyte["positive"]),
                        "type": "Electrolyte",
                        "properties": {"category": "positive", "source": "extraction"}
                    })
                if electrolyte.get("negative"):
                    entities.append({
                        "name": str(electrolyte["negative"]),
                        "type": "Electrolyte",
                        "properties": {"category": "negative", "source": "extraction"}
                    })
                if electrolyte.get("concentration"):
                    entities.append({
                        "name": str(electrolyte["concentration"]),
                        "type": "PerformanceParameter",
                        "properties": {"parameter": "concentration", "source": "extraction"}
                    })
                if electrolyte.get("additives") and isinstance(electrolyte["additives"], list):
                    for additive in electrolyte["additives"]:
                        if additive:
                            entities.append({
                                "name": str(additive),
                                "type": "ChemicalSubstance",
                                "properties": {"source": "extraction"}
                            })
            
            # 提取电极材料
            electrode = materials.get("electrode", {})
            if isinstance(electrode, dict):
                if electrode.get("material"):
                    entities.append({
                        "name": electrode["material"],
                        "type": "ElectrodeMaterial",
                        "properties": {"source": "extraction"}
                    })
                if electrode.get("surface_area"):
                    entities.append({
                        "name": str(electrode["surface_area"]),
                        "type": "PerformanceParameter",
                        "properties": {"parameter": "surface_area", "source": "extraction"}
                    })
            
            # 提取隔膜
            membrane = materials.get("membrane", {})
            if isinstance(membrane, dict):
                if membrane.get("type"):
                    entities.append({
                        "name": membrane["type"],
                        "type": "Membrane",
                        "properties": {"source": "extraction"}
                    })
        
        # 3. 从操作条件提取
        operating_conditions = knowledge.get("operating_conditions", {})
        if isinstance(operating_conditions, dict):
            if operating_conditions.get("temperature"):
                entities.append({
                    "name": str(operating_conditions["temperature"]),
                    "type": "OperatingCondition",
                    "properties": {"parameter": "temperature", "source": "extraction"}
                })
            if operating_conditions.get("concentration"):
                entities.append({
                    "name": operating_conditions["concentration"],
                    "type": "OperatingCondition",
                    "properties": {"parameter": "concentration", "source": "extraction"}
                })
            if operating_conditions.get("current_density"):
                entities.append({
                    "name": operating_conditions["current_density"],
                    "type": "PerformanceParameter",
                    "properties": {"parameter": "current_density", "source": "extraction"}
                })
        
        # 4. 从旧验数据提取
        experimental_data = knowledge.get("experimental_data", [])
        if isinstance(experimental_data, list):
            for exp in experimental_data:
                if isinstance(exp, dict):
                    if exp.get("parameter"):
                        name = f"{exp['parameter']} ({exp.get('unit', '')})".strip()
                        entities.append({
                            "name": name,
                            "type": "ExperimentalData",
                            "properties": {"source": "extraction", "conditions": exp.get("conditions", "")}
                        })
        
        # 5. 从优缺点提取
        advantages = knowledge.get("advantages", [])
        if isinstance(advantages, list):
            for advantage in advantages:
                if advantage:
                    entities.append({
                        "name": str(advantage),
                        "type": "Advantage",
                        "properties": {"source": "extraction"}
                    })
        
        disadvantages = knowledge.get("disadvantages", [])
        if isinstance(disadvantages, list):
            for disadvantage in disadvantages:
                if disadvantage:
                    entities.append({
                        "name": str(disadvantage),
                        "type": "Disadvantage",
                        "properties": {"source": "extraction"}
                    })
        
        # 6. 从应用场景提取
        applications = knowledge.get("applications", [])
        if isinstance(applications, list):
            for app in applications:
                if app:
                    entities.append({
                        "name": str(app),
                        "type": "Application",
                        "properties": {"source": "extraction"}
                    })
        
        # 7. 从关键发现提取
        key_findings = knowledge.get("key_findings", [])
        if isinstance(key_findings, list):
            for finding in key_findings:
                if finding:
                    entities.append({
                        "name": str(finding),
                        "type": "KeyFinding",
                        "properties": {"source": "extraction"}
                    })
        
        # 8. 为有效的实体构建有意义的关系
        self._build_meaningful_relationships(entities, relationships, knowledge)

    def _build_meaningful_relationships(self, entities: list, relationships: list, knowledge: Dict):
        """
        根据实体类型构建有意义的关系。
        """
        # 将实体按类型分组以便快速查找
        entities_by_type = {}
        for entity in entities:
            entity_type = entity["type"]
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # 1. 电极材料 与 操作条件的关系
        if "ElectrodeMaterial" in entities_by_type and "OperatingCondition" in entities_by_type:
            for electrode in entities_by_type["ElectrodeMaterial"]:
                for condition in entities_by_type["OperatingCondition"]:
                    relationships.append({
                        "source": electrode["name"],
                        "target": condition["name"],
                        "type": "USED_UNDER",
                        "properties": {"source": "extraction"}
                    })
        
        # 2. 电解液 与 操作条件的关系
        if "Electrolyte" in entities_by_type and "OperatingCondition" in entities_by_type:
            for electrolyte in entities_by_type["Electrolyte"]:
                for condition in entities_by_type["OperatingCondition"]:
                    relationships.append({
                        "source": electrolyte["name"],
                        "target": condition["name"],
                        "type": "OPERATES_AT",
                        "properties": {"source": "extraction"}
                    })
        
        # 3. 材料 与 性能参数的关系
        if "ElectrodeMaterial" in entities_by_type and "PerformanceParameter" in entities_by_type:
            for electrode in entities_by_type["ElectrodeMaterial"]:
                for perf in entities_by_type["PerformanceParameter"]:
                    relationships.append({
                        "source": electrode["name"],
                        "target": perf["name"],
                        "type": "EXHIBITS",
                        "properties": {"source": "extraction"}
                    })
        
        # 4. 材料 与 旧验数据的关系
        if "ElectrodeMaterial" in entities_by_type and "ExperimentalData" in entities_by_type:
            for electrode in entities_by_type["ElectrodeMaterial"]:
                for exp_data in entities_by_type["ExperimentalData"]:
                    relationships.append({
                        "source": electrode["name"],
                        "target": exp_data["name"],
                        "type": "MEASURED_BY",
                        "properties": {"source": "extraction"}
                    })
        
        # 5. 优点 与 应用场景的关系
        if "Advantage" in entities_by_type and "Application" in entities_by_type:
            for advantage in entities_by_type["Advantage"]:
                for app in entities_by_type["Application"]:
                    relationships.append({
                        "source": advantage["name"],
                        "target": app["name"],
                        "type": "ENABLES",
                        "properties": {"source": "extraction"}
                    })
        
        # 6. 化学物质 与 电解液的关系
        if "ChemicalSubstance" in entities_by_type and "Electrolyte" in entities_by_type:
            for chem in entities_by_type["ChemicalSubstance"]:
                for electrolyte in entities_by_type["Electrolyte"]:
                    relationships.append({
                        "source": chem["name"],
                        "target": electrolyte["name"],
                        "type": "COMPONENT_OF",
                        "properties": {"source": "extraction"}
                    })
        
        # 7. Paper 与 Paper作者的关系
        if "Paper" in entities_by_type and "Author" in entities_by_type:
            for paper in entities_by_type["Paper"]:
                for author in entities_by_type["Author"]:
                    relationships.append({
                        "source": paper["name"],
                        "target": author["name"],
                        "type": "AUTHORED_BY",
                        "properties": {"source": "extraction"}
                    })
        
        # 8. 关键发现 与 应用场景的关系
        if "KeyFinding" in entities_by_type and "Application" in entities_by_type:
            for finding in entities_by_type["KeyFinding"]:
                for app in entities_by_type["Application"]:
                    relationships.append({
                        "source": finding["name"],
                        "target": app["name"],
                        "type": "SUPPORTS",
                        "properties": {"source": "extraction"}
                    })

    def _save_llm_response(self, response_data, para_id: str, status: str = "success", response_type: str = "entities", silent: bool = False):
        """
        将大模型返回的所有数据保存到文件中。
        
        Args:
            response_data: 大模型返回的响应数据（可以是JSON dict、字符串或其他）
            para_id: 段落ID
            status: 响应状态（success/json_decode_error/api_returned_none/api_error_response/socket_timeout/general_exception）
            response_type: 响应类型（"entities" 或 "relations"），用于区分文件名后缀
            silent: 是否静默保存（不输出提示），默认为False。对于entities和relations设为True
        """
        try:
            # 创建保存目录 - 输出到src/graph_rag/llm_responses
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            # 构造文件名（使用段落ID和状态，替换特殊字符）
            # 文件名格式：{文档名}_{response_type}_{状态}.json
            safe_para_id = para_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            filename = os.path.join(save_dir, f"{safe_para_id}_{response_type}_{status}.json")
            
            # 准备保存数据
            save_data = {
                "paragraph_id": para_id,
                "status": status,
                "timestamp": self._get_timestamp(),
                "data": response_data
            }
            
            # 保存为JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 如果不是静默模式，输出提示
            if not silent:
                type_name = "关系" if response_type == "relations" else "实体"
                print(f"    [保存] 提取的{type_name}JSON已保存至 {filename}")
        except Exception as e:
            print(f"    [警告] 保存JSON失败: {str(e)[:100]}")
    
    def _merge_entities_and_relations(self, entities_by_doc: Dict, relations_by_doc: Dict) -> Dict:
        """
        合并第一步（实体提取）和第二步（关系提取）生成的JSON文件。
        为每个文档生成一个合并后的 merged_{doc_id}.json 文件。
        
        Args:
            entities_by_doc: 第一步提取的实体字典 {doc_id: entities_json}
            relations_by_doc: 第二步提取的关系字典 {doc_id: relations_json}
            
        Returns:
            Dict: {doc_id: merged_file_path} 合并后文件的路径映射
        """
        from datetime import datetime
        
        # 输出到src/graph_rag/llm_responses
        save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
        merged_count = 0
        failed_count = 0
        merged_files = {}  # 存储doc_id到合并文件路径的映射
        
        for doc_id in entities_by_doc.keys():
            try:
                # 构造文件名
                safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                entity_file = os.path.join(save_dir, f"{safe_doc_id}_entities_success.json")
                relation_file = os.path.join(save_dir, f"{safe_doc_id}_relations_success.json")
                merged_file = os.path.join(save_dir, f"{safe_doc_id}_merged.json")
                
                # 检查文件是否存在
                # 注释掉：实体和关系文件直接从步骤一和步骤二的API调用保存，这里不再检查
                # if not os.path.exists(entity_file):
                #     print(f"  ⚠️ 实体文件不存在: {entity_file}")
                #     failed_count += 1
                #     continue
                # 
                # if not os.path.exists(relation_file):
                #     print(f"  ⚠️ 关系文件不存在: {relation_file}")
                #     failed_count += 1
                #     continue
                
                # 读取实体JSON文件和关系JSON文件
                # 注释掉：不再单独处理实体和关系文件的读写，直接使用第一步和第二步的提取结果
                try:
                    if os.path.exists(entity_file):
                        with open(entity_file, 'r', encoding='utf-8') as f:
                            entity_wrapper = json.load(f)
                    else:
                        entity_wrapper = {"data": {"entities": []}}
                    
                    if os.path.exists(relation_file):
                        with open(relation_file, 'r', encoding='utf-8') as f:
                            relation_wrapper = json.load(f)
                    else:
                        relation_wrapper = {"data": {"relations": []}}
                except Exception as e:
                    print(f"  ⚠️ 读取文件失败: {str(e)[:50]}，使用空数据继续")
                    entity_wrapper = {"data": {"entities": []}}
                    relation_wrapper = {"data": {"relations": []}}
                
                # 提取实际的数据部分（处理大模型保存的外层结构）
                entity_data = entity_wrapper.get("data", entity_wrapper) if isinstance(entity_wrapper, dict) else entity_wrapper
                relation_data = relation_wrapper.get("data", relation_wrapper) if isinstance(relation_wrapper, dict) else relation_wrapper
                
                # 获取paragraph_id和状态信息
                paragraph_id = entity_wrapper.get("paragraph_id", doc_id)
                entity_status = entity_wrapper.get("status", "unknown")
                relation_status = relation_wrapper.get("status", "unknown")
                merged_status = "success" if entity_status == "success" and relation_status == "success" else "partial"
                
                # 提取entities和relations
                entities = entities_by_doc.get(doc_id, {}).get('entities', []) if isinstance(entities_by_doc.get(doc_id, {}), dict) else []
                relations = relations_by_doc.get(doc_id, {}).get('relations', []) if isinstance(relations_by_doc.get(doc_id, {}), dict) else []
                
                # 构建合并后的数据结构
                merged_data = {
                    "paragraph_id": paragraph_id,
                    "status": merged_status,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data": {
                        "entities": entities,
                        "relations": relations
                    }
                }
                
                # 保存合并后的JSON文件
                with open(merged_file, 'w', encoding='utf-8') as f:
                    json.dump(merged_data, f, ensure_ascii=False, indent=2)
                
                merged_count += 1
                entity_count = len(entities)
                relation_count = len(relations)
                print(f"  ✅ 合并成功: {safe_doc_id}")
                print(f"     实体数: {entity_count}, 关系数: {relation_count}")
                
                # 记录合并文件路径
                merged_files[doc_id] = merged_file
                
            except Exception as e:
                failed_count += 1
                print(f"  ❌ 合并失败 {doc_id}: {str(e)[:100]}")
        
        print(f"\n合并完成: 成功 {merged_count}, 失败 {failed_count}")
        if merged_files:
            sample_doc_id = list(merged_files.keys())[0]
            sample_safe_id = sample_doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            print(f"合并后的JSON文件已保存至 'src/llm_responses/' 目录（文件名: {sample_safe_id}_merged.json）")
        return merged_files
    
    def _validate_merged_json(self, merged_file: str) -> Dict:
        """
        验证合并后的JSON文件质量。
        
        Args:
            merged_file: 合并后JSON文件的路径
            
        Returns:
            Dict: 验证报告
        """
        try:
            import sys
            import io
            sys.path.insert(0, os.path.dirname(__file__))
            from kg_validator_v3 import validate, suggest
            
            # 读取合并后的JSON
            with open(merged_file, 'r', encoding='utf-8') as f:
                kg_wrapper = json.load(f)
            
            # 提取data部分
            kg_data = kg_wrapper.get('data', kg_wrapper) if isinstance(kg_wrapper, dict) else kg_wrapper
            
            # 捕获验证函数的输出
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            # 执行验证
            report = validate(kg_data)
            validation_output = sys.stdout.getvalue()
            
            # 执行建议
            sys.stdout = io.StringIO()
            suggest(kg_data)
            suggestions_output = sys.stdout.getvalue()
            
            sys.stdout = old_stdout
            
            return {
                'report': report,
                'validation_output': validation_output,
                'suggestions_output': suggestions_output,
                'kg_data': kg_data
            }
        except Exception as e:
            print(f"  ❌ 验证失败: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def _generate_validation_report_md(self, doc_id: str, merged_file: str, validation_result: Dict) -> str:
        """
        生成验证报告的Markdown文件。
        
        Args:
            doc_id: 文档ID
            merged_file: 合并文件路径
            validation_result: 验证结果
            
        Returns:
            str: 报告文件路径
        """
        try:
            if 'error' in validation_result:
                report_content = f"# {doc_id} 知识图谱验证报告\n\n验证失败: {validation_result['error']}\n"
            else:
                report = validation_result.get('report', {})
                validation_output = validation_result.get('validation_output', '')
                suggestions_output = validation_result.get('suggestions_output', '')
                
                report_content = f"""# {doc_id} 知识图谱验证报告

## 基本信息
- 合并文件: {merged_file}
- 生成时间: {self._get_timestamp()}

## 验证统计

### 基本指标
- 节点数: {report.get('stats', {}).get('entities', 'N/A')} (目标: 50-80)
- 边数: {report.get('stats', {}).get('relations', 'N/A')} (目标: 100-150)
- 边/节点比: {report.get('stats', {}).get('ratio', 'N/A'):.2f} 
### 错误检查
- 非法实体类型数: {report.get('errors', {}).get('bad_types', 0)}
- 非法关系类型数: {report.get('errors', {}).get('bad_rels', 0)}
- 孤立节点数: {report.get('errors', {}).get('orphans', 0)}
- 孤立Value节点数: {report.get('errors', {}).get('orphan_values', 0)}

### 覆盖率
- 因果关系数: {report.get('coverage', {}).get('causal', 0)}
- Reaction节点数: {report.get('coverage', {}).get('reactions', 0)}
- Species节点数: {report.get('coverage', {}).get('species', 0)}
- Catalyst节点数: {report.get('coverage', {}).get('catalysts', 0)}

## 综合评分

**等级**: {report.get('grade', 'N/A')} (得分: {report.get('score', 0)}/10)

## 详细验证输出

```
{validation_output}
```

## 改进建议

```
{suggestions_output}
```

## 建议行动

"""
                
                # 根据评分添加建议
                score = report.get('score', 0)
                if score >= 8:
                    report_content += "✅ **质量优秀**: 知识图谱质量达到高水平，可直接用于后续步骤。\n"
                elif score >= 6:
                    report_content += "⚠️ **质量中等**: 建议基于验证结果进行重新提取改进。\n"
                else:
                    report_content += "❌ **质量不足**: 强烈建议进行重新提取以改进知识图谱质量。\n"
            
            # 保存报告 - 输出到src/graph_rag/llm_responses
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
            safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            report_file = os.path.join(save_dir, f"{safe_doc_id}_validation_report.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print(f"  ✅ 验证报告已保存: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"  ❌ 生成报告失败: {str(e)[:100]}")
            return None
    
    def _reextract_with_validation_feedback(self, doc_id: str, validation_result: Dict, entities_by_doc: Dict, merged_file: str = None):
        """
        基于验证结果，使用测评报告、合并后的JSON和原始MD文献进行重新提取。
        给大模型三个信息：原始MD文件、合并JSON、测评报告，让大模型直接改进。
        
        Args:
            doc_id: 文档ID
            validation_result: 验证结果
            entities_by_doc: 原始实体提取结果（此参数暂未使用）
            merged_file: 合并后的JSON文件路径
        """
        try:
            print(f"    🔄 基于测评报告进行改进提取...")
            
            # 1. 获取原始Markdown内容
            content = self.documents.get(doc_id)
            if not content:
                print(f"      ❌ 无法找到原始文档内容")
                return None
            
            # 2. 读取合并后的JSON文件（之前的提取结果）
            previous_result = None
            if merged_file and os.path.exists(merged_file):
                try:
                    with open(merged_file, 'r', encoding='utf-8') as f:
                        merged_data = json.load(f)
                    previous_result = merged_data.get('data', merged_data)
                    print(f"      📖 已加载合并JSON结果")
                except Exception as e:
                    print(f"      ⚠️ 无法读取合并文件: {str(e)[:50]}")
            
            # 3. 获取验证报告
            report = validation_result.get('report', {})
            validation_output = validation_result.get('validation_output', '')
            
            # 4. 构建简洁的提示词：原始MD + 合并JSON + 测评报告
            prompt = f"""你是液流电池领域知识图谱提取专家。

基于以下验证测评报告和之前提取的结果，请进行改进提取。

【验证评分】
等级: {report.get('grade', 'N/A')} (得分: {report.get('score', 0)}/10)

【验证详情】
{validation_output}

【上次提取的结果（需要改进）】
```json
{json.dumps(previous_result, ensure_ascii=False, indent=2) if previous_result else '{}'}
```

【原始文献】
{content}

【任务】
请基于验证报告指出的问题，对上次提取的实体和关系进行改进。
输出必须是纯JSON格式：{{"entities": [...], "relations": [...]}}
"""
            
            # 5. 调用API进行改进提取
            print(f"      📨 发送改进提取请求...")
            reextracted_result = self._extract_knowledge_from_paragraph_dashscope(prompt, f"{doc_id}_feedback")
            
            if reextracted_result:
                print(f"      ✅ 基于反馈的改进提取成功")
                
                # 检查返回的数据结构
                has_entities = 'entities' in reextracted_result
                has_relations = 'relations' in reextracted_result
                
                if has_entities:
                    entity_count = len(reextracted_result.get('entities', []))
                    print(f"      🔹 获取到 {entity_count} 个实体")
                else:
                    print(f"      ⚠️ 未获取到实体数据")
                
                if has_relations:
                    relation_count = len(reextracted_result.get('relations', []))
                    print(f"      🔹 获取到 {relation_count} 条关系")
                else:
                    print(f"      ⚠️ 未获取到关系数据")
                
                # 保存改进的结果
                safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                # 输出到src/graph_rag/llm_responses
                save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
                reextract_file = os.path.join(save_dir, f"{safe_doc_id}_reextracted_feedback.json")
                
                with open(reextract_file, 'w', encoding='utf-8') as f:
                    json.dump(reextracted_result, f, ensure_ascii=False, indent=2)
            
                print(f"      💾 改进的结果已保存: {reextract_file}")
                return reextracted_result
            else:
                print(f"      ❌ 基于反馈的改进提取失败")
                return None
            
        except Exception as e:
            print(f"      ❌ 改进提取出错: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_improved_merged_json(self, doc_id: str, reextracted_entities: Dict, extracted_relations: Dict):
        """
        保存基于验证反馈改进后的合并JSON文件。
        
        Args:
            doc_id: 文档ID
            reextracted_entities: 改进后的实体
            extracted_relations: 改进后的关系
        """
        try:
            from datetime import datetime
            
            # 输出到src/graph_rag/llm_responses
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
            safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            
            # 提取entities和relations
            entities = reextracted_entities.get("entities", []) if isinstance(reextracted_entities, dict) else reextracted_entities
            relations = extracted_relations.get("relations", []) if isinstance(extracted_relations, dict) else extracted_relations
            
            # 构建改进后的数据结构
            improved_merged_data = {
                "paragraph_id": doc_id,
                "status": "improved",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": {
                    "entities": entities,
                    "relations": relations
                }
            }
            
            # 保存改进后的合并JSON
            improved_merged_file = os.path.join(save_dir, f"{safe_doc_id}_improved_merged.json")
            with open(improved_merged_file, 'w', encoding='utf-8') as f:
                json.dump(improved_merged_data, f, ensure_ascii=False, indent=2)
            
            entity_count = len(entities)
            relation_count = len(relations)
            print(f"  ✅ 改进后的合并JSON已保存: {improved_merged_file}")
            print(f"     实体数: {entity_count}, 关系数: {relation_count}")
            
        except Exception as e:
            print(f"  ⚠️ 保存改进后的合并JSON失败: {str(e)[:100]}")
    
    def _perform_validation_and_reextraction(self, merged_files: Dict, entities_by_doc: Dict):
        """
        执行验证和改进的循环流程。
        流程：自动检查 → 有ERROR时改进 → 循环检查直到无ERROR → 完成
    
        Args:
            merged_files: {doc_id: merged_file_path} 的字典
            entities_by_doc: 原始实体提取结果
        """
        import sys
        from datetime import datetime
        
        print("\n" + "="*60)
        print("开始进行质量评测和自动改进")
        print("="*60)
        
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from kg_checker import KnowledgeGraphChecker, ReportGenerator
        except ImportError as e:
            print(f"❌ 无法导入kg_checker模块: {e}")
            return
        
        validation_reports = {}
        
        for doc_id, merged_file in merged_files.items():
            print(f"\n【评测】 正在评测 {doc_id}...")
            current_merged_file = merged_file
            iteration = 0
            max_iterations = 2  # 最多修复2次（便于测试）
            
            while iteration < max_iterations:
                iteration += 1
                print(f"\n  🔄 检查迭代 #{iteration}")
                
                # 1. 读取当前的JSON
                try:
                    with open(current_merged_file, 'r', encoding='utf-8') as f:
                        kg_data = json.load(f)
                except Exception as e:
                    print(f"  ❌ 无法读取JSON文件: {e}")
                    break
                
                # 2. 运行检查
                checker = KnowledgeGraphChecker(kg_data)
                result = checker.run_all_checks()
                
                error_count = len(result.get_errors())
                warning_count = len(result.get_warnings())
                
                print(f"  📊 检查结果: {error_count} 个ERROR, {warning_count} 个WARNING")
                
                # 2.5. 保存每次迭代的检查报告为MD文件
                self._save_validation_report_md(doc_id, iteration, result, kg_data)
                
                # 3. 如果没有ERROR，任务完成
                if error_count == 0:
                    print(f"  ✅ 无ERROR，质量检查完成！")
                    validation_reports[doc_id] = {
                        'status': 'success',
                        'iterations': iteration,
                        'error_count': 0,
                        'warning_count': warning_count
                    }
                    break
                
                # 4. 如果还有ERROR，生成修复Prompt
                print(f"  🔧 生成修复Prompt...")
                reporter = ReportGenerator(result, kg_data)
                fix_prompt = reporter.generate_fix_prompt()
                
                # 5. 调用大模型修复
                print(f"  📨 发送修复请求到Kimi...")
                
                # 读取原始文献
                content = self.documents.get(doc_id, "")
                
                # 构建修复提示词
                repair_prompt = f"""你是液流电池领域知识图谱提取专家。

请根据以下检查结果修复知识图谱中的问题。

【检查结果和修复要求】
{fix_prompt}

【原始文献内容】
{content[:20000]}  (如果内容过长已截断)

【修复要求】
1. 仅输出修复后的完整JSON
2. 格式必须是：{{"entities": [...], "relations": [...]}}
3. 确保所有ERROR都被修复
4. 不要输出任何解释文字
"""
                
                fixed_result = self._extract_knowledge_from_paragraph_dashscope(repair_prompt, f"{doc_id}_repair_{iteration}")
                
                if not fixed_result:
                    print(f"  ❌ 修复失败")
                    validation_reports[doc_id] = {
                        'status': 'failed',
                        'iterations': iteration,
                        'error_count': error_count
                    }
                    break
                
                # 6. 保存修复后的JSON
                repaired_data = {
                    "paragraph_id": doc_id,
                    "status": f"repaired_iteration_{iteration}",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data": fixed_result
                }
                
                # 输出到src/graph_rag/llm_responses
                save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
                safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                current_merged_file = os.path.join(save_dir, f"{safe_doc_id}_iteration_{iteration}_merged.json")
                
                with open(current_merged_file, 'w', encoding='utf-8') as f:
                    json.dump(repaired_data, f, ensure_ascii=False, indent=2)
                
                print(f"  💾 修复结果已保存: {current_merged_file}")
                print(f"  🔄 继续下一轮检查...")
        
        # 总结
        print("\n" + "="*60)
        print("评测和改进阶段完成")
        print("="*60)
        
        for doc_id, report_info in validation_reports.items():
            status = report_info.get('status', 'unknown')
            if status == 'success':
                iterations = report_info.get('iterations', 0)
                print(f"✅ {doc_id}: 成功! (耗时 {iterations} 次迭代)")
            else:
                print(f"❌ {doc_id}: 修复失败")
        
        print("\n提示: 可以在 'src/llm_responses/' 目录中查看详细结果")
    
    def _save_validation_report_md(self, doc_id: str, iteration: int, result, kg_data: Dict):
        """
        保存每次迭代的检查报告为MD文件
        
        Args:
            doc_id: 文档ID
            iteration: 迭代次数
            result: KnowledgeGraphChecker的检查结果
            kg_data: 知识图谱数据
        """
        try:
            from kg_checker import ReportGenerator
            
            # 输出到src/graph_rag/llm_responses
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_responses")
            
            # 生成报告
            reporter = ReportGenerator(result, kg_data)
            summary_report = reporter.generate_summary_report()
            
            # 保存为MD文件
            safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            report_file = os.path.join(save_dir, f"{safe_doc_id}_iteration_{iteration}_report.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(summary_report)
            
            print(f"  📄 检查报告已保存: {report_file}")
        except Exception as e:
            print(f"  ⚠️ 保存检查报告失败: {str(e)[:100]}")
    
    def _get_timestamp(self) -> str:
        """
        获取当前时间戳
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _extract_knowledge_from_paragraph_dashscope(self, prompt: str, para_id: str) -> Dict:
        """
        调用 Kimi 模型 API，从单个段落中抽取知识。
        使用 OpenAI 兼容接口调用 Kimi 模型。
        包含重试机制、超时控制和详细的错误处理。
        """
        try:
            from openai import OpenAI
        except ImportError:
            print("错误：未安装 openai 库。请运行 'pip install openai' 安装。")
            return None

        # 配置 API Key
        api_key = os.getenv('DASHSCOPE_API_KEY', __import__("os").environ.get("MOONSHOT_API_KEY", ""))
        if not api_key:
            print("错误：未设置 DASHSCOPE_API_KEY 环境变量。")
            return None

        # 初始化 OpenAI 客户端（使用 Kimi 的 API 端点）
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.cn/v1",
        )

        # 重试配置
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                import time
                
                retry_info = f" (重试 {retry_count}/{max_retries})" if retry_count > 0 else ""
                print(f"    [API调用] 发送请求到 Kimi{retry_info}...")
                start_time = time.time()
                
                # 调用 Kimi API
                response = client.chat.completions.create(
                    model="kimi-k2.6",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1.0,
                    timeout=300,
                )
                
                elapsed_time = time.time() - start_time
                print(f"    [API调用] 响应已收到 (耗时: {elapsed_time:.2f}秒)")
                
                # 获取响应内容
                if response and response.choices and len(response.choices) > 0:
                    json_str = response.choices[0].message.content.strip()
                    print(f"    [API调用] 内容长度: {len(json_str)} 字符")
                    
                    # 移除可能的代码块标记
                    if json_str.startswith("```json"):
                        json_str = json_str[7:].rstrip("` \n")
                    elif json_str.startswith("```"):
                        json_str = json_str[3:].rstrip("` \n")

                    # 尝试解析 JSON
                    try:
                        knowledge = json.loads(json_str)
                        print(f"    [成功] JSON 解析成功")
                        # 注释掉：不保存实体JSON文件（保留在内存处理）
                        # self._save_llm_response(knowledge, para_id, status="success", silent=True)
                        return knowledge
                    except json.JSONDecodeError as e:
                        print(f"    [JSON错误] 解析失败: {str(e)[:100]}")
                        print(f"    [DEBUG] 返回内容前100字: {json_str[:100]}")
                        # 保存解析失败的原始响应
                        self._save_llm_response(json_str, para_id, status="json_decode_error", silent=True)
                        # JSON 解析失败，尝试重试
                        retry_count += 1
                        if retry_count <= max_retries:
                            print(f"    [重试] JSON解析失败，等待后进行第 {retry_count} 次重试...")
                            time.sleep(2 ** retry_count)
                            continue
                        return None
                else:
                    print(f"    [警告] 响应格式异常")
                    self._save_llm_response(None, para_id, status="api_returned_none", silent=True)
                    retry_count += 1
                    if retry_count <= max_retries:
                        print(f"    [重试] 等待后进行第 {retry_count} 次重试...")
                        time.sleep(2 ** retry_count)
                        continue
                    return None
                    
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)[:100]
                print(f"    [异常] {error_type}: {error_msg}")
                
                # 检查是否是网络连接错误
                if "APIConnectionError" in error_type or "ConnectError" in error_type or "Connection" in error_msg:
                    print(f"    ⚠️ 网络连接失败，请检查网络和API端点")
                
                # 保存错误
                self._save_llm_response(str(e), para_id, status="general_exception", silent=True)
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"    [重试] 等待后进行第 {retry_count} 次重试...")
                    time.sleep(2 ** retry_count)
                    continue
                return None
        
        return None

    def _extract_relations_from_paragraph_dashscope(self, prompt: str, para_id: str) -> Dict:
        """
        调用 Kimi 模型 API，从单个段落的实体中抽取关系。
        使用 OpenAI 兼容接口调用 Kimi 模型。
        包含重试机制、超时控制和详细的错误处理。
        """
        try:
            from openai import OpenAI
        except ImportError:
            print("错误：未安装 openai 库。请运行 'pip install openai' 安装。")
            return None

        # 配置 API Key
        api_key = os.getenv('DASHSCOPE_API_KEY', __import__("os").environ.get("MOONSHOT_API_KEY", ""))
        if not api_key:
            print("错误：未设置 DASHSCOPE_API_KEY 环境变量。")
            return None

        # 初始化 OpenAI 客户端（使用 Kimi 的 API 端点）
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.cn/v1",
        )

        # 重试配置
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                import time
                
                retry_info = f" (重试 {retry_count}/{max_retries})" if retry_count > 0 else ""
                print(f"    [API调用] 发送请求到 Kimi 提取关系{retry_info}...")
                start_time = time.time()
                
                # 调用 Kimi API
                response = client.chat.completions.create(
                    model="kimi-k2.6",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1.0,
                    timeout=300,
                )
                
                elapsed_time = time.time() - start_time
                print(f"    [API调用] 响应已收到 (耗时: {elapsed_time:.2f}秒)")
                
                # 获取响应内容
                if response and response.choices and len(response.choices) > 0:
                    json_str = response.choices[0].message.content.strip()
                    print(f"    [API调用] 内容长度: {len(json_str)} 字符")
                    
                    # 移除可能的代码块标记
                    if json_str.startswith("```json"):
                        json_str = json_str[7:].rstrip("` \n")
                    elif json_str.startswith("```"):
                        json_str = json_str[3:].rstrip("` \n")

                    # 尝试解析 JSON
                    try:
                        relations = json.loads(json_str)
                        print(f"    [成功] JSON 解析成功")
                        # 注释掉：不保存关系JSON文件（保留在内存处理）
                        # safe_para_id = para_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                        # self._save_llm_response(relations, para_id, status="success", response_type="relations", silent=True)
                        return relations
                    except json.JSONDecodeError as e:
                        print(f"    [JSON错误] 解析失败: {str(e)[:100]}")
                        print(f"    [DEBUG] 返回内容前100字: {json_str[:100]}")
                        # 保存解析失败的原始响应
                        self._save_llm_response(json_str, para_id, status="json_decode_error", response_type="relations", silent=True)
                        # JSON 解析失败，尝试重试
                        retry_count += 1
                        if retry_count <= max_retries:
                            print(f"    [重试] JSON解析失败，等待后进行第 {retry_count} 次重试...")
                            time.sleep(2 ** retry_count)
                            continue
                        return None
                else:
                    print(f"    [警告] 响应格式异常")
                    self._save_llm_response(None, para_id, status="api_returned_none", response_type="relations", silent=True)
                    retry_count += 1
                    if retry_count <= max_retries:
                        print(f"    [重试] 等待后进行第 {retry_count} 次重试...")
                        time.sleep(2 ** retry_count)
                        continue
                    return None
                    
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)[:100]
                print(f"    [异常] {error_type}: {error_msg}")
                
                # 检查是否是网络连接错误
                if "APIConnectionError" in error_type or "ConnectError" in error_type or "Connection" in error_msg:
                    print(f"    ⚠️ 网络连接失败，请检查网络和API端点")
                
                # 保存错误
                self._save_llm_response(str(e), para_id, status="general_exception", response_type="relations", silent=True)
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"    [重试] 等待后进行第 {retry_count} 次重试...")
                    time.sleep(2 ** retry_count)
                    continue
                return None
        
        return None

    def _update_knowledge_graph(self, knowledge: Dict, para_id: str):
        """
        将从 LLM 抽取的知识更新到全局知识图谱 self.graph 中。
        支持新格式JSON：{"entities": [...], "relations": [...]}
        自动建立跨段落的联通关系。
        """
        if not isinstance(knowledge, dict):
            return
    
    def _update_from_new_format(self, knowledge: Dict, para_id: str):
        """
        从新格式JSON构建图谱。
        格式: {"entities": [{"id": "e1", "name": "...", "type": "...", "aliases": [...]}], 
                "relations": [{"source": "e1", "relation": "...", "target": "e2"}]}
        """
        entities_list = knowledge.get("entities", [])
        relations_list = knowledge.get("relations", [])
        
        if not entities_list:
            print(f"    [调试] 段落 {para_id} 未提取到实体")
            return
        
        # 第一步：创建实体ID映射（JSON中的e1、e2等 -> 图谱中的node_x）
        entity_id_mapping = {}  # {"e1": "node_0", "e2": "node_1", ...}
        name_to_node_id = {}    # {"实体名": "node_0", ...}
        
        # 构建现有实体的名称到ID映射
        for node_id, node in self.graph["nodes"].items():
            name = node["properties"].get("name")
            if name:
                name_to_node_id[name] = node_id
        
        # 处理每个实体
        for entity in entities_list:
            entity_json_id = entity.get("id")  # "e1", "e2", ...
            entity_name = entity.get("name")
            entity_type = entity.get("type", "Entity")
            aliases = entity.get("aliases", [])
            
            if not entity_name:
                continue
            
            # 查找是否已存在该实体（按名称或别名）
            existing_node_id = None
            
            # 先查找主名称
            if entity_name in name_to_node_id:
                existing_node_id = name_to_node_id[entity_name]
            else:
                # 查找别名
                for alias in aliases:
                    if alias in name_to_node_id:
                        existing_node_id = name_to_node_id[alias]
                        break
            
            if existing_node_id:
                # 实体已存在，更新其信息
                node_id = existing_node_id
                node = self.graph["nodes"][node_id]
                
                # 更新别名列表
                if "aliases" not in node["properties"]:
                    node["properties"]["aliases"] = []
                for alias in aliases:
                    if alias not in node["properties"]["aliases"]:
                        node["properties"]["aliases"].append(alias)
            else:
                # 创建新实体
                node_id = f"node_{self.node_counter}"
                self.node_counter += 1
                new_node = {
                    "id": node_id,
                    "label": entity_type,
                    "properties": {
                        "name": entity_name,
                        "aliases": aliases,
                        "source_paragraphs": []
                    }
                }
                self.graph["nodes"][node_id] = new_node
                name_to_node_id[entity_name] = node_id
            
            # 记录映射关系
            entity_id_mapping[entity_json_id] = node_id
            
            # 记录来源段落
            if "source_paragraphs" not in self.graph["nodes"][node_id]["properties"]:
                self.graph["nodes"][node_id]["properties"]["source_paragraphs"] = []
            if para_id not in self.graph["nodes"][node_id]["properties"]["source_paragraphs"]:
                self.graph["nodes"][node_id]["properties"]["source_paragraphs"].append(para_id)
        
        # 第二步：处理关系
        for relation in relations_list:
            source_json_id = relation.get("source")  # "e1"
            target_json_id = relation.get("target")  # "e2"
            rel_type = relation.get("relation")      # "HAS_PROPERTY"
            
            if not all([source_json_id, target_json_id, rel_type]):
                continue
            
            # 转换为实际的node ID
            source_node_id = entity_id_mapping.get(source_json_id)
            target_node_id = entity_id_mapping.get(target_json_id)
            
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
            
            # 创建新关系
            if not existing_edge:
                edge_id = f"edge_{self.edge_counter}"
                self.edge_counter += 1
                new_edge = {
                    "id": edge_id,
                    "source": source_node_id,
                    "target": target_node_id,
                    "relationship": rel_type,
                    "properties": {"source_paragraphs": [para_id]}
                }
                self.graph["edges"][edge_id] = new_edge
            else:
                # 关系已存在，记录额外的来源段落
                if "source_paragraphs" not in existing_edge["properties"]:
                    existing_edge["properties"]["source_paragraphs"] = []
                if para_id not in existing_edge["properties"]["source_paragraphs"]:
                    existing_edge["properties"]["source_paragraphs"].append(para_id)
        
        # 第三步：建立跨段落联通关系（增强图的连通性）
        self._enhance_graph_connectivity(para_id)
    
    def _enhance_graph_connectivity(self, para_id: str):
        """
        增强图的连通性：为相同类型的实体建立关联，确保整个图谱高度连通。
        策略：
        1. 同一段落中不同类型的实体建立 RELATED_TO 关系
        2. 不同段落中相同或相关类型的实体建立跨段落关系
        """
        # 获取当前段落相关的所有节点
        para_nodes = []
        for node_id, node in self.graph["nodes"].items():
            source_paras = node["properties"].get("source_paragraphs", [])
            if para_id in source_paras:
                para_nodes.append((node_id, node))
        
        # 为相同类型的实体（来自不同段落）建立关系
        type_nodes = {}
        for node_id, node in self.graph["nodes"].items():
            node_type = node["label"]
            if node_type not in type_nodes:
                type_nodes[node_type] = []
            type_nodes[node_type].append((node_id, node))
        
        # 建立相同类型实体之间的关系（增强连通性）
        for node_type, nodes in type_nodes.items():
            if len(nodes) > 1:
                # 为同类型实体建立关系
                for i in range(len(nodes)):
                    for j in range(i + 1, len(nodes)):
                        node1_id, node1 = nodes[i]
                        node2_id, node2 = nodes[j]
                        
                        # 检查是否已存在关系
                        rel_exists = False
                        for edge_id, edge in self.graph["edges"].items():
                            if ((edge["source"] == node1_id and edge["target"] == node2_id) or
                                (edge["source"] == node2_id and edge["target"] == node1_id)):
                                rel_exists = True
                                break
                        
                        if not rel_exists:
                            # 建立关系
                            edge_id = f"edge_{self.edge_counter}"
                            self.edge_counter += 1
                            
                            # 根据类型选择关系
                            rel_type = "RELATED_TO"
                            if node_type == "Property":
                                rel_type = "ASSOCIATED_WITH"
                            elif node_type == "Value":
                                rel_type = "LINKED_TO"
                            
                            new_edge = {
                                "id": edge_id,
                                "source": node1_id,
                                "target": node2_id,
                                "relationship": rel_type,
                                "properties": {"type": "connectivity_enhancement", "source_paragraphs": [para_id]}
                            }
                            self.graph["edges"][edge_id] = new_edge
    
    def _update_from_old_format(self, knowledge: Dict, para_id: str):
        """
        从旧格式JSON构建图谱（兼容原有逻辑）。
        """
        # 将中文格式的 API 响应转换为实体和关系列表
        entities = []
        relationships = []
        
        # 解析 JSON 结构并提取实体和关系
        self._parse_extraction_knowledge(knowledge, entities, relationships)
        
        # 如果没有实体，打印调试信息
        if not entities:
            print(f"    [调试] 段落 {para_id} 未提取到实体")
            return
            
        # 临时映射：实体名 -> 节点ID（用于快速查找，避免重复）
        name_to_id = {node["properties"].get("name"): node_id for node_id, node in self.graph["nodes"].items()}

        for entity_data in entities:
            entity_name = entity_data.get("name")
            if not entity_name:
                continue

            # 实体已存在：直接获取ID
            if entity_name in name_to_id:
                node_id = name_to_id[entity_name]
            # 实体不存在：创建新节点
            else:
                node_id = f"node_{self.node_counter}"
                self.node_counter += 1
                new_node = {
                    "id": node_id,
                    "label": entity_data.get("type", "Entity"),
                    "properties": entity_data.get("properties", {})
                }
                # 确保实体名存在于属性中
                if "name" not in new_node["properties"]:
                    new_node["properties"]["name"] = entity_name
                self.graph["nodes"][node_id] = new_node
                name_to_id[entity_name] = node_id
            
            # 记录实体来源段落（用于溯源）
            if "source_paragraphs" not in self.graph["nodes"][node_id]["properties"]:
                self.graph["nodes"][node_id]["properties"]["source_paragraphs"] = []
            if para_id not in self.graph["nodes"][node_id]["properties"]["source_paragraphs"]:
                self.graph["nodes"][node_id]["properties"]["source_paragraphs"].append(para_id)

        # 处理关系 (Relationships) - 使用之前解析的 relationships
        for rel_data in relationships:
            source_name = rel_data.get("source")
            target_name = rel_data.get("target")
            rel_type = rel_data.get("type")

            # 跳过参数不完整的关系
            if not all([source_name, target_name, rel_type]):
                continue

            # 确保源实体和目标实体都已存在于图谱中
            if source_name in name_to_id and target_name in name_to_id:
                source_id = name_to_id[source_name]
                target_id = name_to_id[target_name]

                # 检查关系是否已存在，避免重复
                existing_edge = None
                for edge_id, edge in self.graph["edges"].items():
                    if (edge["source"] == source_id and 
                        edge["target"] == target_id and 
                        edge["relationship"] == rel_type):
                        existing_edge = edge
                        break

                # 如果关系不存在，则创建新关系
                if not existing_edge:
                    edge_id = f"edge_{self.edge_counter}"
                    self.edge_counter += 1
                    new_edge = {
                        "id": edge_id,
                        "source": source_id,
                        "target": target_id,
                        "relationship": rel_type,
                        "properties": rel_data.get("properties", {})
                    }
                    self.graph["edges"][edge_id] = new_edge
                else:
                    # 如果关系已存在，合并属性
                    if "properties" in rel_data:
                        existing_edge["properties"].update(rel_data["properties"])

# 使用示例
if __name__ == "__main__":
    # 使用相对于项目根目录的路径
    DATA_DIRECTORY = "extraction_results"

    # 初始化GraphRAG
    graph_rag = GraphRAG(DATA_DIRECTORY)

    
