# GraphMind

基于微软 [GraphRAG](https://github.com/microsoft/graphrag) 的知识图谱构建与可视化问答平台。上传文本文件即可自动抽取实体/关系，构建知识图谱，支持交互式力导向图可视化和多种模式的智能问答。

## 功能特性

- **文件上传与解析** — 支持 .txt / .md / .csv / .docx / .pdf 等常见文本格式
- **实体关系抽取** — 调用 LLM 自动识别实体、关系及社区结构，生成 GraphRAG 索引
- **交互式图谱可视化** — 基于 ECharts 的力导向图，支持拖拽、缩放、节点筛选与聚焦
- **多模式智能问答** — 本地搜索 / 全局搜索 / 基础 RAG 三种检索模式，流式输出
- **数据集管理** — 创建、切换、删除数据集，每个数据集独立索引互不干扰

## 目录结构

```
demo_app/
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 应用入口，CORS / 生命周期配置
│   │   ├── config.py            # 配置管理（YAML 加载与环境变量）
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic 数据模型（请求/响应/数据集/图谱实体）
│   │   ├── routers/
│   │   │   ├── datasets.py      # 数据集 CRUD API
│   │   │   ├── documents.py     # 文件上传 / 管理 API
│   │   │   ├── indexing.py      # GraphRAG 索引构建 / 进度 API
│   │   │   ├── graph.py         # 图谱数据 / 实体详情 / 关系查询 API
│   │   │   └── search.py        # 多模式搜索 / 问答 API（SSE 流式）
│   │   ├── services/
│   │   │   ├── dataset_service.py   # 数据集业务逻辑
│   │   │   ├── document_service.py  # 文档解析与管理
│   │   │   ├── indexing_service.py  # GraphRAG 索引编排
│   │   │   ├── graph_service.py     # 图谱数据读取与组装
│   │   │   └── search_service.py    # 搜索策略与 LLM 调用
│   │   └── utils/
│   │       ├── prompts.py           # 提示词模板（实体类型发现等）
│   │       ├── file_parser.py       # 多格式文件解析器
│   │       └── settings_generator.py # GraphRAG settings.yaml 生成
│   ├── tests/                   # 后端单元测试
│   ├── config.template.yaml     # LLM 配置模板（可提交）
│   ├── config.local.yaml        # 私密配置（已 gitignore）
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                    # React + Vite + Ant Design 前端
│   └── src/
│       ├── main.tsx             # 应用入口
│       ├── App.tsx              # 路由配置
│       ├── pages/
│       │   ├── Layout.tsx           # 全局布局（侧边栏导航）
│       │   ├── DatasetManager.tsx   # 数据集管理页
│       │   ├── DataBrowser.tsx      # 文件浏览页
│       │   ├── GraphView.tsx        # 图谱可视化页
│       │   └── SearchQA.tsx         # 智能问答页
│       ├── services/
│       │   └── api.ts           # Axios 封装，后端 API 调用
│       ├── stores/
│       │   ├── datasetStore.ts  # 数据集状态管理（Zustand）
│       │   └── searchStore.ts   # 搜索状态管理（Zustand）
│       └── assets/              # 静态资源（图标、图片）
├── data/                        # 运行时数据（已 gitignore）
│   └── {dataset_id}/
│       ├── input/               # 上传的原始文件
│       ├── output/              # GraphRAG 索引输出 (.parquet)
│       └── settings.yaml        # 数据集级 GraphRAG 配置
├── doc/                         # 设计文档与截图
├── test/                        # API 集成测试
├── start.sh                     # 一键启动脚本
├── pyproject.toml
└── README.md
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 知识图谱 | Microsoft GraphRAG |
| 前端框架 | React 18 + TypeScript |
| 构建工具 | Vite |
| UI 组件库 | Ant Design 5 |
| 图谱可视化 | ECharts (force 布局) |
| 状态管理 | Zustand |
| HTTP 客户端 | Axios |
| 包管理 | uv (Python) / npm (Node.js) |

## 快速开始

### 环境要求

- Python 3.11+ / [uv](https://docs.astral.sh/uv/)
- Node.js 18+ / npm

### 1. 配置 LLM

```bash
cd backend
cp config.template.yaml config.local.yaml
# 编辑 config.local.yaml，填入你的 API Key 和模型配置
```

```yaml
# backend/config.local.yaml（不提交到 git）
llm:
  api_key: "sk-***"                                              # 必填
  model: "qwen-plus"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"

embedding:
  model: "text-embedding-v3"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

支持所有兼容 OpenAI API 格式的服务（OpenAI、通义千问、DeepSeek 等）。

### 2. 一键启动

```bash
./start.sh
```

启动后访问:

- 前端界面: http://localhost:5777
- 后端 API 文档: http://localhost:8777/docs

按 `Ctrl+C` 停止所有服务。

### 3. 手动启动（可选）

```bash
# 终端 1 — 启动后端
cd backend && uv sync && uv run uvicorn app.main:app --port 8777

# 终端 2 — 启动前端
cd frontend && npm install && npm run dev
```

## 使用流程

1. **创建数据集** — 在"数据集管理"页面创建一个新的数据集
2. **上传文件** — 向数据集中上传文本文件（.txt / .md / .csv / .pdf / .docx）
3. **构建索引** — 点击"构建图谱"，GraphRAG 自动调用 LLM 抽取实体和关系
4. **图谱可视化** — 在"图谱预览"页面以交互式力导向图查看实体关系网络
5. **智能问答** — 在"搜索问答"页面选择搜索模式进行提问

### 搜索模式对比

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 本地搜索 | 基于实体关联扩展上下文 | 聚焦特定实体的具体问题 |
| 全局搜索 | 基于社区摘要的全局搜索 | 宏观概括性问题 |
| 基础 RAG | 基于文档块向量检索 | 需要原始文本片段支撑 |

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/datasets` | 创建数据集 |
| `GET` | `/api/datasets` | 获取数据集列表 |
| `DELETE` | `/api/datasets/{id}` | 删除数据集 |
| `POST` | `/api/datasets/{id}/documents` | 上传文件 |
| `GET` | `/api/datasets/{id}/documents` | 文件列表 |
| `DELETE` | `/api/datasets/{id}/documents/{doc_id}` | 删除文件 |
| `POST` | `/api/datasets/{id}/index` | 构建图谱索引 |
| `GET` | `/api/datasets/{id}/index/status` | 索引状态（SSE） |
| `GET` | `/api/datasets/{id}/graph` | 获取图谱数据 |
| `GET` | `/api/datasets/{id}/graph/nodes/{label}` | 实体详情 |
| `POST` | `/api/datasets/{id}/search` | 搜索问答（SSE 流式） |

## 测试

```bash
# 后端单元测试
cd backend && uv run pytest

# API 集成测试（需先启动后端）
cd test && bash api_test.sh
```

## License

MIT
