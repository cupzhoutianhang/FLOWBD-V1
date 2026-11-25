# FlowBD：中文文献问答与方法关联追溯

系统代码、案例与论文补充材料。GitHub仓库地址：https://github.com/cupzhoutianhang/FLOWBD-V1。

## 使用

```powershell
python -m pip install -r requirements-demo.txt
.\start_frontend.ps1
```

默认入口为frontend_app.py。实时问答需自行配置模型、索引、数据库和服务，详见docs/SETUP.md。

## 文件目录

- frontend/、frontend_app.py：新版前端。
- src/：检索、问答及方法关联代码。
- paper/：交互案例数据。
- supplementary_materials/：专题文献与统计、关系订正、历史问答、实验记录、两位专家评分及统计代码。
- media/demo/：演示视频与动图。
- docs/：使用、上传与数据说明。

## 数据说明

两位专家评分与论文统计一致，综合均分2.740和3.775，差值按四舍五入显示为1.04。石蜡材料提供历史回答及检索来源定位，不含检索片段全文。论文图4的文献对应说明与前端案例分别提供。历史文件及版本范围见supplementary_materials/README.md。

AO_E008已从活动案例关系中排除，原因保留在排除记录中。数据库、文献全文、模型权重和密钥不随包提供。历史运行环境未完整打包。

视频较大，上传方式见docs/GITHUB_UPLOAD.md。第三方组件许可见THIRD_PARTY_NOTICES.md。欢迎反馈问题、补充专题案例和贡献代码。
