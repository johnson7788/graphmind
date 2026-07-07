# GraphMind API 文档

基于 FastAPI 的后端接口。所有接口以 `/api` 为前缀。

- **Base URL**：`http://localhost:8777`
- **交互式文档**：`http://localhost:8777/docs`（Swagger UI）
- **请求/响应体**：默认 `application/json`（文件上传为 `multipart/form-data`）
- **数据集标识**：`dataset_id`，创建时由后端生成（`名称清洗 + _6位hex`）

## 接口总览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/datasets` | 数据集列表 |
| POST | `/api/datasets` | 创建数据集 |
| GET | `/api/datasets/{dataset_id}` | 数据集详情 |
| DELETE | `/api/datasets/{dataset_id}` | 删除数据集 |
| POST | `/api/datasets/{dataset_id}/documents` | 上传文档 |
| GET | `/api/datasets/{dataset_id}/documents` | 文档列表 |
| DELETE | `/api/datasets/{dataset_id}/documents/{filename}` | 删除文档 |
| POST | `/api/datasets/{dataset_id}/index` | 启动索引构建 |
| GET | `/api/datasets/{dataset_id}/index/status` | 轮询索引状态 |
| POST | `/api/datasets/{dataset_id}/discover-entity-types` | LLM 自动发现实体类型 |
| GET | `/api/config/status` | LLM 配置状态 |
| POST | `/api/config/check-api` | 检查 Chat/Embedding API 连通性 |
| GET | `/api/datasets/{dataset_id}/graph` | 图谱数据（节点+边） |
| GET | `/api/datasets/{dataset_id}/graph/stats` | 图谱统计 |
| GET | `/api/datasets/{dataset_id}/graph/search-entities` | 实体名称模糊搜索 |
| GET | `/api/datasets/{dataset_id}/graph/neighborhood` | 实体邻域子图 |
| GET | `/api/datasets/{dataset_id}/graph/image` | 多模态实体截图 |
| GET | `/api/datasets/{dataset_id}/entities` | 实体分页列表 |
| GET | `/api/datasets/{dataset_id}/relationships` | 关系分页列表 |
| GET | `/api/datasets/{dataset_id}/entity` | 单个实体精确查询 |
| GET | `/api/datasets/{dataset_id}/relationship` | 单条关系精确查询 |
| POST | `/api/datasets/{dataset_id}/search` | 智能问答（非流式） |
| POST | `/api/datasets/{dataset_id}/search/stream` | 智能问答（SSE 流式） |
| POST | `/api/datasets/{dataset_id}/search/context` | 纯检索（不生成答案） |

---

## 健康检查

### GET `/api/health`

**响应**
```json
{ "status": "ok" }
```

---

## 数据集 Datasets

### GET `/api/datasets`
列出所有数据集（最新在前）。

**响应** `DatasetListResponse`
```json
{
  "datasets": [
    {
      "id": "demo_a1b2c3",
      "name": "示例",
      "created": "2026-07-07T10:00:00",
      "has_index": true,
      "index_complete": true,
      "entity_count": 223,
      "relationship_count": 499
    }
  ]
}
```

### POST `/api/datasets`
创建数据集。`id` 由 `name` 清洗后拼接 6 位随机 hex 生成。

**请求体** `DatasetCreate`
```json
{ "name": "示例" }
```
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 显示名称，1–100 字符 |

**响应** `201` `DatasetInfo`（见上）。

### GET `/api/datasets/{dataset_id}`
获取单个数据集详情。**响应** `DatasetInfo`。

### DELETE `/api/datasets/{dataset_id}`
删除整个数据集（含 input/rag_storage/output）。

**响应**
```json
{ "deleted": true }
```

---

## 文档 Documents

### POST `/api/datasets/{dataset_id}/documents`
上传一个或多个文档（`multipart/form-data`，字段名 `files`）。原始文件保留，构建索引时由 MinerU 解析。

**支持格式**：
`.pdf` · 图片 `.jpg/.jpeg/.png/.bmp/.tiff/.tif/.gif/.webp` · Office `.doc/.docx/.ppt/.pptx/.xls/.xlsx` · 文本 `.txt/.md/.csv`

**响应** `UploadResponse`
```json
{
  "uploaded": 1,
  "documents": [
    { "name": "示例文档.pdf", "size": 1048576, "extracted_chars": 0 }
  ]
}
```

### GET `/api/datasets/{dataset_id}/documents`
列出数据集 `input/` 目录下的所有文档。

**响应** `DocumentListResponse`
```json
{
  "dataset_id": "demo_a1b2c3",
  "documents": [ { "name": "示例文档.pdf", "size": 1048576, "extracted_chars": 0 } ]
}
```

### DELETE `/api/datasets/{dataset_id}/documents/{filename}`
删除数据集内的单个文档。**响应** `{ "deleted": true }`。

---

## 索引 Indexing

### POST `/api/datasets/{dataset_id}/index`
启动索引构建（后台线程），立即返回初始状态，随后轮询 `/index/status`。

**请求体** `IndexRequest`
```json
{ "entity_types": ["person", "organization"], "entity_type_mode": "manual" }
```
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| entity_types | string[] \| null | 否 | 抽取实体类型；`null` 使用默认集 |
| entity_type_mode | string | 否 | `default` \| `manual` \| `auto` |

**响应** `IndexStatus`（见下）。

### GET `/api/datasets/{dataset_id}/index/status`
轮询索引进度（建议每 2–3 秒一次）。

**响应** `IndexStatus`
```json
{
  "dataset_id": "demo_a1b2c3",
  "status": "running",
  "step": "building",
  "progress": 62,
  "message": "[1/1] 处理多模态内容（3 项）：示例文档.pdf",
  "error": null
}
```
| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | `idle` \| `running` \| `completed` \| `failed` |
| step | string | 当前阶段 |
| progress | int | 0–100 |
| message | string | 进度描述 |
| error | string \| null | 失败原因 |

### POST `/api/datasets/{dataset_id}/discover-entity-types`
调用 LLM 从样本文本自动发现实体类型。

**请求体** `DiscoverEntityTypesRequest`
```json
{ "sample_text": "至少 10 个字符的样本文本…" }
```

**响应** `DiscoverEntityTypesResponse`
```json
{ "entity_types": ["disease", "drug", "organ", "symptom"] }
```

---

## 配置 Config

### GET `/api/config/status`
返回 LLM 是否已正确配置。

**响应** `ConfigStatus`
```json
{
  "configured": true,
  "model": "qwen-plus",
  "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "emb_model": "text-embedding-v3"
}
```

### POST `/api/config/check-api`
检测 Chat 与 Embedding API 端点连通性（无请求体）。

**响应** `ApiCheckResponse`
```json
{
  "chat_ok": true,
  "embedding_ok": true,
  "chat_error": null,
  "embedding_error": null
}
```

---

## 图谱 Graph

### GET `/api/datasets/{dataset_id}/graph`
返回用于可视化的图谱数据（节点 + 边）。

**查询参数**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| types | string | `""` | 逗号分隔的实体类型过滤，如 `image,chart` |
| limit | int | 200 | 节点上限，1–2000 |

**响应** `GraphData`
```json
{
  "nodes": [
    {
      "id": "示例产品®",
      "label": "示例产品®",
      "type": "artifact",
      "description": "……",
      "color": "#636E72",
      "size": 32.0,
      "image": "output/示例文档_aa5dd441/示例文档/hybrid_ocr/images/xxx.jpg"
    }
  ],
  "edges": [
    { "from": "135#", "to": "正式准入医院", "label": "……", "weight": 1.0 }
  ]
}
```
> `image` 仅多模态节点（image/table/chart/equation）解析到截图时存在；用其值请求 `graph/image` 接口获取图片。

### GET `/api/datasets/{dataset_id}/graph/stats`
返回图谱统计。

**响应** `GraphStats`
```json
{
  "entity_count": 223,
  "relationship_count": 499,
  "entity_types": { "artifact": 40, "concept": 55, "image": 1, "chart": 2 }
}
```

### GET `/api/datasets/{dataset_id}/graph/search-entities`
实体名称模糊搜索（用于实体浏览器）。

**查询参数**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| q | string | — | 搜索词，必填，≥1 字符 |
| limit | int | 20 | 返回上限，1–100 |

**响应**
```json
[ { "name": "示例产品®", "type": "artifact" } ]
```

### GET `/api/datasets/{dataset_id}/graph/neighborhood`
返回某实体 N 级邻域子图。

**查询参数**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| entity | string | — | 实体名称，必填 |
| depth | int | 3 | 邻域深度，1–5 |

**响应** `GraphData`（同 `/graph`）。

### GET `/api/datasets/{dataset_id}/graph/image`
返回多模态实体的截图文件（路径经数据集根目录校验）。

**查询参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| path | string | 数据集相对图片路径（取自节点的 `image` 字段），必填 |

**响应**：图片文件（`FileResponse`）。找不到或越权返回 `404`。

### GET `/api/datasets/{dataset_id}/entities`
实体分页列表。

**查询参数**：`page`（默认 1，≥1）、`page_size`（默认 20，1–200）。

**响应** `PaginatedResponse`
```json
{
  "items": [ { "title": "示例产品®", "type": "artifact", "description": "……" } ],
  "total": 223,
  "page": 1,
  "page_size": 20
}
```

### GET `/api/datasets/{dataset_id}/relationships`
关系分页列表。参数同上。

**响应** `PaginatedResponse`
```json
{
  "items": [ { "source": "135#", "target": "正式准入医院", "description": "……", "weight": 1.0 } ],
  "total": 499,
  "page": 1,
  "page_size": 20
}
```

### GET `/api/datasets/{dataset_id}/entity`
按名称精确查询单个实体（图节点属性 + 邻接实体名）。

**查询参数**：`name`（实体名称，必填）。找不到返回 `404`。

**响应**
```json
{
  "name": "示例产品®",
  "properties": {
    "entity_id": "示例产品®",
    "entity_type": "artifact",
    "description": "……",
    "source_id": "chunk-xxx",
    "file_path": "示例文档.pdf"
  },
  "neighbors": [ "正式准入医院", "135#" ]
}
```

### GET `/api/datasets/{dataset_id}/relationship`
按源/目标实体精确查询单条关系。

**查询参数**：`source`、`target`（均必填）。找不到返回 `404`。

**响应**
```json
{
  "source": "135#",
  "target": "正式准入医院",
  "properties": {
    "description": "……",
    "keywords": "……",
    "weight": 1.0,
    "source_id": "chunk-xxx"
  }
}
```

---

## 智能问答 Search

请求体 `SearchRequest`（两个接口通用）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 问题文本，≥1 字符 |
| mode | string | 否 | 检索模式，默认 `mix`；见下表。`basic` 为 `naive` 的别名 |
| multimodal_content | dict[] \| null | 否 | 附带的多模态内容（图片/表格/公式），触发 VLM 增强问答 |

**检索模式**

| mode | 界面标签 | 检索方式 |
|------|----------|----------|
| `mix` | 混合检索 | 图谱 + 向量（hybrid 之上叠加向量文本块），最全面（默认） |
| `local` | 本地搜索 | 以实体为中心 |
| `global` | 全局搜索 | 以关系为中心 |
| `hybrid` | 混合模式 | local + global，均在图谱内 |
| `naive` | 基础 RAG | 纯向量检索，不使用知识图谱 |

### POST `/api/datasets/{dataset_id}/search`
非流式问答。

**请求体**
```json
{ "query": "示例产品的市场策略是什么？", "mode": "mix" }
```

**响应** `SearchResponse`
```json
{
  "query": "示例产品的市场策略是什么？",
  "mode": "mix",
  "answer": "……",
  "context": null
}
```

### POST `/api/datasets/{dataset_id}/search/context`
纯检索，只返回命中的上下文（实体/关系/文本块），不调用 LLM 生成答案。`mode` 同上表。

**请求体**
```json
{ "query": "示例产品的市场策略是什么？", "mode": "mix" }
```
> `multimodal_content` 在此接口忽略。

**响应**
```json
{
  "query": "示例产品的市场策略是什么？",
  "mode": "mix",
  "context": "-----Entities-----\n……\n-----Relationships-----\n……\n-----Sources-----\n……"
}
```

### POST `/api/datasets/{dataset_id}/search/stream`
SSE 流式问答。`Content-Type: text/event-stream`。

**请求体**：同上。

**事件类型**
| event | data | 说明 |
|-------|------|------|
| status | `{ "status": "...", "message": "..." }` | 进度更新 |
| chunk | `{ "text": "..." }` | 增量答案文本 |
| done | `{ "query": "...", "mode": "...", "answer": "..." }` | 最终结果 |
| error | `{ "message": "..." }` | 出错 |

> 注：附带 `multimodal_content` 触发 VLM 增强时为非流式路径，仅在 `chunk`/`done` 中返回完整结果。
