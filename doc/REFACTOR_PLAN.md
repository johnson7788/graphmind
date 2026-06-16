# GraphRAG Demo → 前后端分离改造计划

## 一、当前架构

```
┌─────────────────────────────────────────────┐
│              Streamlit (app.py ~1205行)      │
│  ┌───────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 文件  │ │ 知识图谱 │ │ 智能问答/数据 │  │
│  │ 上传  │ │ 可视化   │ │ 浏览          │  │
│  └───┬───┘ └────┬─────┘ └──────┬────────┘  │
│      │          │              │            │
│      ▼          ▼              ▼            │
│  ┌──────────────────────────────────────┐   │
│  │   GraphRAG Core (直接 Python 调用)   │   │
│  │   - 索引管线 (indexing pipeline)     │   │
│  │   - 查询引擎 (local/global/basic)    │   │
│  │   - 向量存储 (LanceDB)              │   │
│  │   - 表格存储 (Parquet)              │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**技术栈**: Python 3.11+ / Streamlit / Microsoft GraphRAG ≥2.0 / pyvis+vis.js / LanceDB / Parquet / 阿里云DashScope(qwen-plus) / uv

**核心问题**: 单文件1200行，无 REST API 层，前后端耦合，无法独立部署和扩展。

---

## 二、目标架构

```
┌──────────────────────────────┐     ┌──────────────────────────────────────┐
│       Frontend (Vite+React)  │     │        Backend (Python FastAPI)      │
│                              │     │                                      │
│  ┌──────────┐ ┌──────────┐  │     │  ┌────────────────────────────┐     │
│  │ 文件上传 │ │ 图谱可视化│  │     │  │     FastAPI REST API       │     │
│  │ 页面     │ │ 页面     │  │     │  │  /api/datasets             │     │
│  └──────────┘ └──────────┘  │     │  │  /api/documents            │     │
│  ┌──────────┐ ┌──────────┐  │ HTTP│  │  /api/indexing             │     │
│  │ 智能问答 │ │ 数据浏览 │  │◄───►│  │  /api/search               │     │
│  │ 页面     │ │ 页面     │  │     │  │  /api/graph                │     │
│  └──────────┘ └──────────┘  │     │  └────────────┬───────────────┘     │
│                              │     │               │                     │
│  Tech:                       │     │  ┌────────────▼───────────────┐     │
│  - React 18 + TypeScript     │     │  │    Service Layer           │     │
│  - Vite                      │     │  │  - DatasetService          │     │
│  - React Router              │     │  │  - IndexingService         │     │
│  - Zustand (状态管理)        │     │  │  - SearchService           │     │
│  - Axios                     │     │  │  - GraphService            │     │
│  - Ant Design                │     │  └────────────┬───────────────┘     │
│  - vis-network (图谱可视化)  │     │               │                     │
│  - react-markdown            │     │  ┌────────────▼───────────────┐     │
│                              │     │  │    GraphRAG Core (保留)    │     │
└──────────────────────────────┘     │  │  - indexing pipeline       │     │
                                     │  │  - query engines           │     │
                                     │  │  - LanceDB vectors         │     │
                                     │  │  - Parquet storage         │     │
                                     │  └────────────────────────────┘     │
                                     └──────────────────────────────────────┘
```

---

## 三、项目目录结构

```
graphrag-demo/
├── frontend/                          # Vite + React 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx                   # 入口
│       ├── App.tsx                    # 路由配置
│       ├── pages/
│       │   ├── Layout.tsx            # 全局布局（侧边栏+内容区）
│       │   ├── DatasetManager.tsx    # 数据集管理（上传+构建）
│       │   ├── GraphView.tsx         # 知识图谱可视化
│       │   ├── SearchQA.tsx          # 智能问答
│       │   └── DataBrowser.tsx       # 数据浏览
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx
│       │   │   └── Header.tsx
│       │   ├── dataset/
│       │   │   ├── FileUploader.tsx
│       │   │   ├── DatasetSelector.tsx
│       │   │   ├── EntityTypeConfig.tsx
│       │   │   └── IndexingProgress.tsx
│       │   ├── graph/
│       │   │   ├── GraphCanvas.tsx   # vis-network 力导向图
│       │   │   ├── GraphToolbar.tsx
│       │   │   └── NodeDetail.tsx
│       │   ├── search/
│       │   │   ├── SearchInput.tsx
│       │   │   ├── SearchResult.tsx  # Markdown 渲染
│       │   │   └── SearchHistory.tsx
│       │   └── data/
│       │       ├── EntityTable.tsx
│       │       ├── RelationTable.tsx
│       │       └── CommunityTable.tsx
│       ├── services/
│       │   └── api.ts                # Axios 封装
│       ├── stores/
│       │   ├── datasetStore.ts       # Zustand
│       │   ├── searchStore.ts
│       │   └── graphStore.ts
│       └── hooks/
│           ├── useIndexing.ts        # SSE 进度 hook
│           └── useSearch.ts
│
├── backend/                           # Python FastAPI 后端
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── config.yaml
│   ├── config.local.yaml             # gitignored
│   └── app/
│       ├── main.py                   # FastAPI 入口 + CORS
│       ├── config.py                 # 配置加载
│       ├── routers/
│       │   ├── datasets.py           # /api/datasets
│       │   ├── documents.py          # /api/documents
│       │   ├── indexing.py           # /api/indexing
│       │   ├── search.py             # /api/search
│       │   └── graph.py              # /api/graph
│       ├── services/
│       │   ├── dataset_service.py
│       │   ├── document_service.py
│       │   ├── indexing_service.py
│       │   ├── search_service.py
│       │   └── graph_service.py
│       ├── models/
│       │   └── schemas.py            # Pydantic 模型
│       └── utils/
│           ├── file_parser.py        # PDF/DOCX/TXT 解析
│           ├── prompts.py            # 中文 prompt 模板
│           └── settings_generator.py # settings.yaml 生成
│
└── data/                              # 运行时数据（兼容现有结构）
    └── <dataset_id>/
        ├── .demo_meta.yaml
        ├── settings.yaml
        ├── input/
        ├── output/  (parquet + lancedb)
        ├── cache/
        ├── prompts/
        └── logs/
```

---

## 四、后端 API 设计

### 4.1 数据集管理
| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/datasets` | 获取所有数据集列表 |
| `POST` | `/api/datasets` | 创建新数据集 |
| `GET` | `/api/datasets/{id}` | 获取数据集详情 |
| `DELETE` | `/api/datasets/{id}` | 删除数据集 |

### 4.2 文档管理
| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/api/datasets/{id}/documents` | 上传文件（multipart） |
| `GET` | `/api/datasets/{id}/documents` | 列出已上传文件 |
| `DELETE` | `/api/datasets/{id}/documents/{name}` | 删除文件 |

### 4.3 索引构建
| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/api/datasets/{id}/index` | 启动索引构建 |
| `GET` | `/api/datasets/{id}/index/status` | 索引状态（SSE 推送） |
| `GET` | `/api/datasets/{id}/index/log` | 获取索引日志 |
| `POST` | `/api/datasets/{id}/discover-entity-types` | LLM 自动发现实体类型 |

### 4.4 图谱查询
| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/datasets/{id}/graph` | 获取图谱数据（nodes+edges JSON） |
| `GET` | `/api/datasets/{id}/graph/stats` | 图谱统计 |
| `GET` | `/api/datasets/{id}/entities` | 实体列表（分页） |
| `GET` | `/api/datasets/{id}/relationships` | 关系列表（分页） |
| `GET` | `/api/datasets/{id}/communities` | 社区报告列表 |
| `GET` | `/api/datasets/{id}/communities/{cid}` | 社区报告详情 |

### 4.5 智能搜索
| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/api/datasets/{id}/search` | 执行搜索 `{query, mode}` |

### 4.6 配置
| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/config/status` | LLM 配置状态 |
| `POST` | `/api/config/check-api` | 验证 LLM API 连通性 |

---

## 五、代码迁移映射（app.py → 后端模块）

| app.py 函数 | → 迁移目标 |
|-------------|-----------|
| `_load_config()` | `backend/app/config.py` |
| `_get_data_dir()` | `backend/app/config.py` |
| `_list_datasets()`, `_load_dataset_meta()` | `services/dataset_service.py` |
| `_parse_uploaded_file()` | `utils/file_parser.py` |
| `_discover_entity_types()` | `services/indexing_service.py` |
| `_generate_settings_yaml()` | `utils/settings_generator.py` |
| `_write_chinese_prompts()` | `utils/prompts.py` |
| `_check_api_connectivity()` | `services/indexing_service.py` |
| `_run_index()` | `services/indexing_service.py` |
| `_load_graph_data()`, `_build_pyvis_graph()` | `services/graph_service.py`（改为返回 JSON） |
| `_run_search()` | `services/search_service.py` |
| `_load_parquet_safe()` | 各 service 内部使用 |

---

## 六、关键技术决策

### 6.1 图谱可视化：后端 JSON → 前端 vis-network

**现状**: pyvis 在服务端生成完整 HTML，通过 `st.components.v1.html()` 嵌入。

**改造**: 后端返回 `{nodes: [...], edges: [...]}` JSON，前端用 `vis-network` 渲染。

```typescript
// 图谱数据格式
interface GraphData {
  nodes: Array<{
    id: string; label: string; type: string;
    description: string; color: string; size: number;
  }>;
  edges: Array<{
    from: string; to: string; label: string; weight: number;
  }>;
}
```

### 6.2 索引进度推送：SSE (Server-Sent Events)

**现状**: Streamlit `st.progress()` 同步更新。

**改造**: 后端索引在后台线程运行，通过 SSE 实时推送：
```
GET /api/datasets/{id}/index/status → text/event-stream
data: {"step": "extract_graph", "progress": 45, "message": "..."}
```

### 6.3 文件上传：multipart/form-data

前端 Axios `FormData`，后端 FastAPI `UploadFile`。

### 6.4 数据分页

Parquet 数据通过 pandas 加载后分页返回，避免大数据集一次全部加载。

---

## 七、分步实施计划

### Phase 1: 项目骨架搭建
- [ ] 创建 `frontend/` — Vite + React + TypeScript 初始化
- [ ] 安装前端依赖: react-router-dom, axios, antd, zustand, vis-network, react-markdown
- [ ] 创建 `backend/` — 迁移 pyproject.toml，添加 fastapi + uvicorn + sse-starlette
- [ ] 搭建 FastAPI 骨架 (main.py + CORS + 路由注册)
- [ ] 定义 Pydantic schemas

### Phase 2: 后端核心服务迁移
- [ ] `config.py` — 配置加载
- [ ] `dataset_service.py` — 数据集 CRUD
- [ ] `document_service.py` — 文件上传与解析
- [ ] `indexing_service.py` — GraphRAG 索引管线 + SSE 进度 + 实体类型发现
- [ ] `prompts.py` — 中文 prompt 模板迁移
- [ ] `settings_generator.py` — settings.yaml 生成逻辑迁移

### Phase 3: 后端查询服务
- [ ] `graph_service.py` — 图谱数据查询（返回 JSON nodes+edges）
- [ ] `search_service.py` — 三种搜索模式迁移
- [ ] 所有 router 路由实现

### Phase 4: 前端页面开发
- [ ] Layout + 路由（Sidebar 导航）
- [ ] DatasetManager 页面（FileUploader + EntityTypeConfig + IndexingProgress + DatasetSelector）
- [ ] GraphView 页面（GraphCanvas + GraphToolbar + NodeDetail）
- [ ] SearchQA 页面（SearchInput + SearchResult + SearchHistory）
- [ ] DataBrowser 页面（EntityTable + RelationTable + CommunityTable）

### Phase 5: 联调与优化
- [ ] 前后端联调测试
- [ ] 错误处理完善
- [ ] 加载状态优化（骨架屏、loading）
- [ ] 图谱可视化调优（颜色、物理引擎、暗色主题）
- [ ] 响应式布局

---

## 八、依赖清单

### Backend
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "python-multipart>=0.0.9",
    "sse-starlette>=2.0",
    "graphrag>=2.0",
    "pandas>=2.0",
    "pyarrow>=14",
    "pyyaml>=6.0",
    "pypdf2>=3.0",
    "python-docx>=1.0",
]
```

### Frontend
```json
{
  "dependencies": {
    "react": "^18", "react-dom": "^18",
    "react-router-dom": "^6", "axios": "^1",
    "antd": "^5", "zustand": "^4",
    "vis-network": "^9", "vis-data": "^7",
    "react-markdown": "^9", "remark-gfm": "^4"
  },
  "devDependencies": {
    "typescript": "^5", "vite": "^5",
    "@vitejs/plugin-react": "^4", "@types/react": "^18"
  }
}
```

---

## 九、开发启动命令

```bash
# 后端 (port 8000)
cd backend && uv sync
uv run uvicorn app.main:app --reload --port 8000

# 前端 (port 5173, proxy /api → :8000)
cd frontend && npm install && npm run dev
```
