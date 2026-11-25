# 运行配置

先在独立环境安装 requirements-demo.txt，执行根目录 start_frontend.ps1，访问 http://localhost:8510 。前端浏览不要求先初始化模型；完整问答另安装 requirements.txt 并准备相应基础设施。依赖清单不是经过干净环境验证的锁定文件。

PowerShell 设置：

```powershell
$env:MOONSHOT_API_KEY = '<your-key>'
$env:METASO_API_KEY = '<your-metaso-key>'
$env:NEO4J_PASSWORD = '<your-database-password>'
$env:NEO4J_PWD = $env:NEO4J_PASSWORD
.\start_frontend.ps1
```

.env.example 仅列出变量，不会自动加载 .env。新版发送副本中的 API 占位符与已识别数据库密码已接入上述环境变量；Metaso 与 Moonshot 分别配置。

完整问答需要本地 BGE-M3/reranker 模型、Milvus、Neo4j、对应语料、方法索引与审计资料。公开包不附带数据库卷和文献全文。论文评价的历史回答、评分、映射及统计位于supplementary_materials；这些文件不等于实时运行所需的完整数据库和环境。

检索代码支持 src/data/corpus_versions/active.json；本包不自动启用师弟的新 collection。未配置该清单时回退 traditional_rag_collection_v5。如需采用新 collection，应先核对数据库、tokenizer、IDF 与语料的对应关系，不能单独复制清单。

原版评测页读取仓库父目录下 qa_runs，未附带该私密目录时会提示不可用。全量谱系、证据补充与部分审计功能也需要额外数据。

TypeScript 源码随组件一起提供；要重建时进入 frontend/component，运行 npm ci、npm run check、npm run build。
