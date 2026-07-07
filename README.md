# GraphMind

基于 [LightRAG](https://github.com/HKUDS/LightRAG) 与 [RAG-Anything](https://github.com/HKUDS/RAG-Anything) 的知识图谱构建与可视化问答平台。上传文档（含 PDF / 图片 / 表格 / 公式等多模态内容）即可通过 MinerU 解析并自动抽取实体/关系，构建知识图谱，支持交互式力导向图可视化和多种模式的智能问答。

## 功能特性

- **多模态文档解析** — 基于 MinerU，支持 PDF / 图片 / Office / .txt / .md / .csv 等，自动提取文本、图片、表格、公式
- **实体关系抽取** — 调用 LLM 自动识别实体与关系，写入 LightRAG 知识图谱存储
- **交互式图谱可视化** — 基于 sigma.js + graphology 的力导向图，支持缩放、筛选、图片节点缩略图显示、双击节点展开邻域探索
- **多模式智能问答** — naive / local / global / hybrid / mix 五种检索模式，流式输出；支持图片等多模态内容的 VLM 增强问答
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
│   │   │   ├── indexing.py      # 索引构建 / 进度 API
│   │   │   ├── graph.py         # 图谱数据 / 实体详情 / 关系查询 / 图片 API
│   │   │   └── search.py        # 多模式搜索 / 问答 API（SSE 流式）
│   │   └── services/
│   │       ├── rag_engine.py        # LightRAG / RAG-Anything 实例管理
│   │       ├── dataset_service.py   # 数据集业务逻辑
│   │       ├── document_service.py  # 文档上传与管理
│   │       ├── indexing_service.py  # RAG-Anything (MinerU) 索引编排
│   │       ├── graph_service.py     # 图谱数据读取与组装
│   │       └── search_service.py    # 检索策略与 LLM/VLM 调用
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
│       ├── rag_storage/         # LightRAG 知识图谱存储 (graphml + kv/vector)
│       └── output/              # MinerU 解析输出（图片、表格等多模态资源）
├── doc/                         # 设计文档与截图
├── test/                        # API 集成测试
├── start.sh                     # 一键启动脚本
├── prepare.sh                   # 后端环境准备脚本（分步安装依赖 + 模型下载）
├── pyproject.toml
└── README.md
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 知识图谱 | LightRAG + RAG-Anything |
| 文档解析 | MinerU（多模态） |
| 前端框架 | React 19 + TypeScript |
| 构建工具 | Vite |
| UI 组件库 | Ant Design 6 |
| 图谱可视化 | sigma.js + graphology (forceAtlas2 布局) |
| 状态管理 | Zustand |
| HTTP 客户端 | Axios |
| 包管理 | uv (Python) / npm (Node.js) |

## 快速开始

### 环境要求

- Python 3.12+ / [uv](https://docs.astral.sh/uv/)
- Node.js 18+ / npm

### 1. 准备后端环境

```bash
./prepare.sh                # 安装依赖 + 预下载 MinerU 模型（约几 GB）
./prepare.sh --skip-models  # 仅安装依赖，首次构建图谱时再自动下载模型
```

> **为什么不用 `uv sync`：** raganything 钉了 `lightrag-hku<1.5`，与我们使用的 1.5.4 冲突。`prepare.sh` 通过分步 `uv pip install` + `--no-deps` 绕过。

### 2. 配置 LLM

```bash
cd backend
# 编辑 config.local.yaml（prepare.sh 已从模板自动生成），填入你的 API Key
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

rag:
  language: "简体中文"   # 实体/关系抽取的输出语言；不设置时 LightRAG 默认英文
```

支持所有兼容 OpenAI API 格式的服务（OpenAI、通义千问、DeepSeek 等）。

### 3. 一键启动

```bash
./start.sh
```

启动后访问:

- 前端界面: http://localhost:5777
- 后端 API 文档: http://localhost:8777/docs

按 `Ctrl+C` 停止所有服务。

### 4. 手动启动（可选）

```bash
# 终端 1 — 启动后端（先确认已运行过 prepare.sh）
cd backend && uv run uvicorn app.main:app --port 8777

# 终端 2 — 启动前端
cd frontend && npm install && npm run dev
```

## 使用流程

1. **创建数据集** — 在"数据集管理"页面创建一个新的数据集
2. **上传文件** — 向数据集中上传文档（.pdf / 图片 / .docx / .txt / .md / .csv 等）
3. **构建索引** — 点击"构建图谱"，MinerU 解析文档、LightRAG 自动调用 LLM 抽取实体和关系
4. **图谱可视化** — 在"图谱预览"页面以交互式力导向图查看实体关系网络，双击节点可展开其邻域
5. **智能问答** — 在"搜索问答"页面选择检索模式进行提问

### 搜索模式对比

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| mix | 图谱 + 向量混合检索 | 通用默认，综合效果最佳 |
| local | 基于实体关联扩展上下文 | 聚焦特定实体的具体问题 |
| global | 基于全局关系的检索 | 宏观概括性问题 |
| hybrid | local + global 结合 | 兼顾细节与全局 |
| naive | 基于文档块向量检索 | 需要原始文本片段支撑 |

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
| `GET` | `/api/datasets/{id}/index/status` | 索引状态 |
| `GET` | `/api/datasets/{id}/graph` | 获取图谱数据 |
| `GET` | `/api/datasets/{id}/graph/neighborhood` | 实体邻域子图 |
| `GET` | `/api/datasets/{id}/graph/image` | 图片节点缩略图 |
| `POST` | `/api/datasets/{id}/search` | 搜索问答 |
| `POST` | `/api/datasets/{id}/search/stream` | 搜索问答（SSE 流式） |

## 测试

```bash
# 后端单元测试
cd backend && uv run pytest

# API 集成测试（需先启动后端）
cd test && bash api_test.sh
```

## License

MIT
