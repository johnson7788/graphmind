# GraphMind — 项目文件说明

## 目录结构总览

```
demo_app/
├── backend/                          # 后端（FastAPI + GraphRAG）
│   ├── app/
│   │   ├── models/                   # 数据模型
│   │   ├── routers/                  # API 路由层
│   │   ├── services/                 # 业务逻辑层
│   │   ├── utils/                    # 工具函数
│   │   ├── config.py                 # 配置加载器
│   │   └── main.py                   # FastAPI 应用入口
│   ├── config.yaml                   # LLM/Embedding 配置模板
│   ├── config.local.yaml             # 本地配置（填入 API Key，已 gitignore）
│   └── pyproject.toml                # 后端 Python 依赖声明
├── frontend/                         # 前端（React + Vite + Ant Design）
│   ├── src/
│   │   ├── assets/                   # 静态资源（图片、图标）
│   │   ├── pages/                    # 页面组件
│   │   ├── services/                 # API 请求封装
│   │   ├── stores/                   # 状态管理（Zustand）
│   │   ├── App.tsx                   # 路由配置根组件
│   │   ├── main.tsx                  # React 应用入口
│   │   └── index.css                 # 全局样式
│   ├── package.json                  # 前端 Node.js 依赖声明
│   └── vite.config.ts                # Vite 构建配置（端口、API 代理）
├── lib/                              # 第三方静态库（vis-network、tom-select）
├── test/                             # 测试脚本
├── doc/                              # 文档目录
├── data/                             # 运行时数据（数据集、索引产物）
├── app.py                            # Streamlit 版单体应用（旧版入口）
├── config.yaml                       # 项目根配置模板
├── config.local.yaml                 # 项目根本地配置
├── pyproject.toml                    # 根级 Python 依赖（Streamlit 版）
└── start.sh                          # 一键启动前后端脚本
```

---

## 后端核心文件 (`backend/`)

### 应用入口与配置

| 文件 | 用途 |
|------|------|
| `app/main.py` | **FastAPI 应用入口**。创建 FastAPI 实例，注册 CORS 中间件，挂载所有路由模块。服务默认监听 8777 端口 |
| `app/config.py` | **配置加载器**。读取 `config.local.yaml`（优先）或 `config.yaml`，解析 LLM/Embedding 的 API Key、模型名、端点地址；定义数据根目录 `DATA_ROOT` 和默认实体类型列表；提供 `get_llm_config()` 和 `is_config_valid()` 校验函数 |
| `config.yaml` | **配置模板**。定义 LLM 模型（默认 qwen-plus）和 Embedding 模型（默认 text-embedding-v3）的连接参数，需复制为 `config.local.yaml` 后填入真实 API Key |
| `pyproject.toml` | **Python 依赖声明**。后端核心依赖：FastAPI、uvicorn、graphrag≥2.0、pandas、pyarrow、PyPDF2、python-docx 等 |

### 数据模型 (`app/models/`)

| 文件 | 用途 |
|------|------|
| `schemas.py` | **Pydantic 数据模型定义**。包含全部请求/响应 Schema：`DatasetCreate/Info`（数据集）、`DocumentInfo/UploadResponse`（文档）、`IndexRequest/IndexStatus`（索引构建）、`GraphNode/GraphEdge/GraphData/GraphStats`（图谱可视化）、`SearchRequest/SearchResponse`（问答搜索）、`PaginatedResponse`（分页数据） |

### API 路由层 (`app/routers/`)

| 文件 | 用途 |
|------|------|
| `datasets.py` | **数据集管理路由**。提供数据集的列表、创建、删除接口 |
| `documents.py` | **文档管理路由**。处理文件上传（支持 .txt/.md/.csv/.pdf/.docx）、文档列表查询、单文档删除 |
| `indexing.py` | **索引构建路由**。触发 GraphRAG 索引构建流程（SSE 实时推送进度）、实体类型自动发现、配置状态查询、API 连通性检查 |
| `graph.py` | **图谱可视化路由**。返回图谱节点和边数据（支持按实体类型过滤和数量限制）、图谱统计信息、分页浏览实体/关系/社区数据 |
| `search.py` | **智能问答路由**。支持三种搜索模式：local（实体邻域检索）、global（社区摘要全局检索）、basic（基础 RAG 文本块检索） |

### 业务逻辑层 (`app/services/`)

| 文件 | 用途 |
|------|------|
| `dataset_service.py` | **数据集服务**。实现数据集的 CRUD 操作：扫描 `data/` 目录列出数据集、创建数据集目录、读取 Parquet 文件统计实体/关系/社区数量、判断索引状态 |
| `document_service.py` | **文档服务**。处理文件上传（编码检测、UTF-8 转码）、文档列表查询（含字符数统计）、文件删除，支持格式校验 |
| `graph_service.py` | **图谱服务**。从 Parquet 文件加载实体/关系/社区数据，为前端可视化构建节点和边；包含实体类型配色方案（`TYPE_COLORS`）；提供分页数据查询 |
| `indexing_service.py` | **索引服务（核心）**。在后台线程中执行 `graphrag index` 命令，通过 SSE 实时推送构建进度；负责生成 `settings.yaml` 和 `prompts/` 目录；支持实体类型自动发现（调用 LLM 分析样本）和 API 连通性检测 |
| `search_service.py` | **搜索服务**。封装 `graphrag.api` 的搜索函数，根据模式（local/global/basic）加载所需 Parquet 表并执行知识图谱检索问答 |

### 工具函数 (`app/utils/`)

| 文件 | 用途 |
|------|------|
| `file_parser.py` | **文件解析器**。从不同格式文件中提取纯文本：PDF（PyPDF2）、DOCX（python-docx）、TXT/MD/CSV（UTF-8 解码） |
| `prompts.py` | **Prompt 模板生成器**。写入语言自适应的 GraphRAG 索引 Prompt（`prompts/` 目录），支持中英文输出，包含实体抽取、关系抽取、社区报告生成等 Prompt |
| `settings_generator.py` | **Settings 生成器**。根据 LLM 配置和实体类型列表，自动生成 GraphRAG v3.x 格式的 `settings.yaml` 配置文件，包含模型端点、Embedding 配置、存储路径等 |

---

## 前端核心文件 (`frontend/`)

### 应用入口

| 文件 | 用途 |
|------|------|
| `main.tsx` | **React 应用入口**。挂载 React 根组件到 DOM，使用 StrictMode |
| `App.tsx` | **路由配置**。使用 React Router + Ant Design ConfigProvider，定义四个页面路由：`/datasets`（数据集管理）、`/graph`（知识图谱）、`/search`（智能问答）、`/data`（数据浏览） |
| `index.css` | **全局样式** |
| `index.html` | **HTML 入口模板** |

### 页面组件 (`src/pages/`)

| 文件 | 用途 |
|------|------|
| `Layout.tsx` | **全局布局组件**。侧边栏导航菜单（数据集管理、知识图谱、智能问答、数据浏览），使用 Ant Design Layout + Menu |
| `DatasetManager.tsx` | **数据集管理页面**。创建/删除数据集、上传文档、管理文件列表、配置实体类型、触发 GraphRAG 索引构建（实时进度条）、查看构建状态 |
| `GraphView.tsx` | **知识图谱可视化页面**。使用 vis-network 渲染交互式力导向图，支持按实体类型过滤、节点数量控制、节点详情抽屉、图谱统计信息展示 |
| `SearchQA.tsx` | **智能问答页面**。输入自然语言问题，选择搜索模式（local/global/basic），展示 LLM 生成的答案和上下文，支持搜索历史记录 |
| `DataBrowser.tsx` | **数据浏览页面**。以表格形式分页浏览实体、关系、社区数据，支持社区详情查看 |

### API 服务 (`src/services/`)

| 文件 | 用途 |
|------|------|
| `api.ts` | **API 请求统一封装**。基于 axios 创建客户端（baseURL `/api`，超时 5 分钟），封装所有后端接口调用：数据集 CRUD、文档上传/列表/删除、索引触发、实体类型发现、图谱数据/统计、实体/关系/社区分页查询、搜索问答、配置状态检查 |

### 状态管理 (`src/stores/`)

| 文件 | 用途 |
|------|------|
| `datasetStore.ts` | **数据集状态 Store**（Zustand）。管理数据集列表、当前选中数据集 ID、加载状态，提供 `fetchDatasets()` 和 `selectDataset()` 方法 |
| `searchStore.ts` | **搜索结果状态 Store**（Zustand）。管理搜索结果历史列表和当前结果，提供添加结果、设置当前结果、清空历史等操作 |

### 构建与配置

| 文件 | 用途 |
|------|------|
| `package.json` | **前端依赖声明**。核心依赖：React 19、Ant Design 6、vis-network（图谱可视化）、axios、react-router-dom 7、react-markdown、zustand（状态管理）、remark-gfm（Markdown 渲染） |
| `vite.config.ts` | **Vite 构建配置**。开发服务器端口 5777，API 请求代理到后端 `localhost:8777`，特别配置了 SSE（Server-Sent Events）代理支持 |

---

## 根目录文件

| 文件 | 用途 |
|------|------|
| `start.sh` | **一键启动脚本**。自动检查 uv 和 node 环境、安装依赖、并行启动后端（8777）和前端（5777），Ctrl+C 统一停止所有服务 |
| `app.py` | **Streamlit 版单体应用（旧版）**。将上传文件、构建图谱、可视化、问答集成在单一 Streamlit 页面中，适合快速演示 |
| `config.yaml` | **根级配置模板**（与 `backend/config.yaml` 相同，供旧版 `app.py` 使用） |
| `pyproject.toml` | **根级依赖声明**。供 Streamlit 版 `app.py` 使用，依赖 streamlit、graphrag、pyvis 等 |

---

## 第三方库 (`lib/`)

| 目录 | 用途 |
|------|------|
| `vis-9.1.2/` | vis-network 图谱可视化库（CSS + JS），供旧版 Streamlit 页面使用 |
| `tom-select/` | Tom Select 下拉选择增强库（JS + CSS） |
| `bindings/utils.js` | 工具绑定脚本 |

---

## 测试 (`test/`)

| 文件 | 用途 |
|------|------|
| `api_test.sh` | Shell API 测试脚本，用于 curl 调用后端接口 |
| `test_api.py` | Python API 测试脚本 |
