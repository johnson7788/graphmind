 GraphRAG Demo 前后端分离改造计划

 Context

 当前项目是一个 单文件 Streamlit 应用 (app.py, ~1205行)，封装了 Microsoft GraphRAG 的完整知识图谱流程。没有 REST
 API、没有独立前端、无法分别部署和扩展。需要改造为标准的前后端分离架构：Vite+React 前端 + Python FastAPI 后端。

 用户选择: 当前目录下新建 frontend/ + backend/，Ant Design UI，SSE 进度推送。

 改造总览

 demo_app/
 ├── app.py                    # 保留原文件作参考
 ├── frontend/                 # 新建 - Vite + React + TypeScript
 ├── backend/                  # 新建 - FastAPI + GraphRAG Core
 ├── data/                     # 保留 - 运行时数据（兼容现有结构）
 └── REFACTOR_PLAN.md          # 已生成的详细计划文档

 Phase 1: 后端骨架 + 配置 (backend/)

 关键文件: app.py 中的 _load_config(), _get_data_dir()

 步骤:

 1. 创建 backend/pyproject.toml — 基于现有 pyproject.toml，添加 fastapi/uvicorn/sse-starlette/python-multipart
 2. 创建 backend/app/__init__.py
 3. 创建 backend/app/config.py — 迁移配置加载逻辑 (从 app.py L31-L66)
 4. 创建 backend/app/models/schemas.py — 所有 Pydantic 请求/响应模型
 5. 创建 backend/app/main.py — FastAPI 入口，CORS 中间件，lifespan，路由注册
 6. 复制 config.yaml 和 config.local.yaml 到 backend/

 Phase 2: 后端数据集 + 文档服务

 迁移自: app.py 的 _list_datasets(), _load_dataset_meta(), _parse_uploaded_file(), 文件上传逻辑

 步骤:

 1. backend/app/services/dataset_service.py:
   - list_datasets() → 扫描 data/ 目录，返回 {id, name, has_index} 列表
   - get_dataset(id) → 读取 .demo_meta.yaml
   - create_dataset(id, name) → 创建目录 + meta 文件
   - delete_dataset(id) → 删除整个目录
 2. backend/app/utils/file_parser.py:
   - 迁移 _parse_uploaded_file() 逻辑 — 支持 .txt/.md/.csv/.pdf/.docx
   - PDF 用 PyPDF2，DOCX 用 python-docx
 3. backend/app/services/document_service.py:
   - upload_documents(dataset_id, files) → 解析并保存到 data/{id}/input/
   - list_documents(dataset_id) → 列出 input/ 下文件
   - delete_document(dataset_id, filename) → 删除文件
 4. backend/app/routers/datasets.py — GET/POST/DELETE /api/datasets
 5. backend/app/routers/documents.py — POST/GET/DELETE /api/datasets/{id}/documents

 Phase 3: 后端索引服务 + SSE 进度

 迁移自: app.py 的 _run_index(), _discover_entity_types(), _generate_settings_yaml(), _write_chinese_prompts(), _check_api_connectivity()

 步骤:

 1. backend/app/utils/prompts.py — 迁移 _write_chinese_prompts() 中的所有 prompt 模板（约 200 行中/英文 prompt）
 2. backend/app/utils/settings_generator.py — 迁移 _generate_settings_yaml() 逻辑
 3. backend/app/services/indexing_service.py:
   - start_indexing(dataset_id, entity_types) → 后台线程运行 GraphRAG 索引
   - get_status(dataset_id) → 返回当前索引状态
   - discover_entity_types(dataset_id) → LLM 自动发现实体类型
   - check_api_connectivity() → 验证 LLM API
   - 索引状态通过内存字典追踪，SSE endpoint 轮询推送
 4. backend/app/routers/indexing.py:
   - POST /api/datasets/{id}/index — 启动索引
   - GET /api/datasets/{id}/index/status — SSE 流
   - POST /api/datasets/{id}/discover-entity-types
   - POST /api/config/check-api
   - GET /api/config/status

 Phase 4: 后端图谱 + 搜索服务

 迁移自: app.py 的 _load_graph_data(), _build_pyvis_graph(), _run_search(), _load_parquet_safe()

 步骤:

 1. backend/app/services/graph_service.py:
   - get_graph_data(dataset_id, types, limit) → 返回 {nodes: [...], edges: [...]} JSON
   - 节点颜色按 entity type 分配（复用 _ENTITY_TYPE_COLORS 映射）
   - 节点大小按连接数计算
   - get_entities(dataset_id, page, size) → 分页返回实体
   - get_relationships(dataset_id, page, size) → 分页返回关系
   - get_communities(dataset_id) → 返回社区报告列表
   - get_community_detail(dataset_id, community_id) → 返回单个报告 JSON
 2. backend/app/services/search_service.py:
   - search(dataset_id, query, mode) → 调用 graphrag.api.local_search/global_search/basic_search
   - 返回 {answer: str, context: str} 格式
 3. backend/app/routers/graph.py — GET /api/datasets/{id}/graph, /entities, /relationships, /communities
 4. backend/app/routers/search.py — POST /api/datasets/{id}/search

 Phase 5: 前端项目初始化

 步骤:

 1. cd frontend && npm create vite@latest . -- --template react-ts
 2. 安装依赖: react-router-dom, axios, antd, @ant-design/icons, zustand, vis-network, vis-data, react-markdown, remark-gfm
 3. 配置 vite.config.ts:
   - proxy /api → http://localhost:8000
   - proxy /api/datasets/*/index/status → SSE 透传
 4. 配置 Ant Design 中文 locale
 5. 创建基础布局 Layout.tsx — Ant Design Layout + Menu 侧边栏

 Phase 6: 前端页面 — 数据集管理

 组件:

 - DatasetManager.tsx — 主页面
 - FileUploader.tsx — Ant Design Upload.Dragger，支持多文件拖拽上传
 - EntityTypeConfig.tsx — Radio 切换 (默认/手动/自动) + Tag 输入
 - IndexingProgress.tsx — SSE 连接 + Ant Design Steps + Progress
 - DatasetSelector.tsx — Ant Design Select 切换数据集

 交互流程:

 1. 选择/创建数据集 → 上传文件 → 配置实体类型 → 点击构建
 2. SSE 接收进度事件，实时更新 Steps 和 Progress 组件
 3. 构建完成后自动切换到图谱页

 Phase 7: 前端页面 — 图谱可视化

 组件:

 - GraphView.tsx — 主页面
 - GraphCanvas.tsx — vis-network Network 组件
   - 力导向布局，forceAtlas2Based 物理引擎
   - 暗色背景 #1a1a2e（与原版一致）
   - 节点按 type 着色，按连接数设置大小
   - 点击节点弹出详情面板
 - GraphToolbar.tsx — Ant Design Select 类型筛选 + Slider 节点数量限制
 - NodeDetail.tsx — Ant Design Drawer 展示节点详情

 Phase 8: 前端页面 — 智能问答

 组件:

 - SearchQA.tsx — 主页面
 - SearchInput.tsx — Ant Design Input.Search + Radio.Group 搜索模式
 - SearchResult.tsx — react-markdown 渲染答案
 - SearchHistory.tsx — Ant Design Timeline 展示历史记录

 Phase 9: 前端页面 — 数据浏览

 组件:

 - DataBrowser.tsx — 主页面，Ant Design Tabs
 - EntityTable.tsx — Ant Design Table，列: 名称/类型/描述/ID，分页
 - RelationTable.tsx — 列: 源/目标/描述/权重/ID，分页
 - CommunityTable.tsx — 列: 标题/评分/ID，点击行展开 JSON 详情 (Ant Design Modal + Tree)

 Phase 10: 联调 + 样式优化

 1. 前后端 API 联调，确保所有接口正常工作
 2. 全局错误处理: Axios 拦截器统一提示，Ant Design message 组件
 3. Loading 状态: 各操作加 Spin / Skeleton
 4. 图谱暗色主题微调
 5. 删除原 app.py（或保留为 app_legacy.py 参考）

 关键文件清单（从 app.py 迁移的代码位置）

 ┌────────────────────┬─────────────┬──────────────────────────────────────────┐
 │        功能        │ app.py 行号 │                 迁移目标                 │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 配置加载           │ L31-66      │ backend/app/config.py                    │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 数据集管理         │ L68-112     │ backend/app/services/dataset_service.py  │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 文件解析           │ L114-158    │ backend/app/utils/file_parser.py         │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 实体类型发现       │ L160-218    │ backend/app/services/indexing_service.py │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ settings.yaml 生成 │ L220-355    │ backend/app/utils/settings_generator.py  │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 中文 prompt 模板   │ L357-535    │ backend/app/utils/prompts.py             │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 索引管线           │ L537-616    │ backend/app/services/indexing_service.py │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 图谱构建+可视化    │ L618-741    │ backend/app/services/graph_service.py    │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ 搜索引擎           │ L743-790    │ backend/app/services/search_service.py   │
 ├────────────────────┼─────────────┼──────────────────────────────────────────┤
 │ UI 布局+交互       │ L792-1205   │ frontend/src/ 各组件                     │
 └────────────────────┴─────────────┴──────────────────────────────────────────┘

 验证方案

 1. 后端验证: uv run uvicorn app.main:app --reload 启动后访问 http://localhost:8000/docs 查看 Swagger UI，逐个测试 API
 2. 前端验证: npm run dev 启动后完整走一遍流程：创建数据集 → 上传文件 → 配置实体类型 → 构建图谱 → 查看图谱 → 问答 → 数据浏览
 3. 端到端验证: 使用原有的测试数据，对比 Streamlit 版本和分离版本的输出结果是否一致
