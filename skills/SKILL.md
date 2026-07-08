---
name: graphmind-search
description: 查询 GraphMind 知识图谱 RAG 后端——智能问答、纯检索取上下文、按实体/关系精确查询、模糊搜实体、取实体邻域子图。当用户想在自己构建的知识图谱里检索、问答、查某个实体或两个实体间的关系、或提到 GraphMind / 知识图谱数据集 / graphmind 后端时，务必使用本 skill，即使没有明说“调用 API”。
---

# GraphMind 知识图谱检索

GraphMind 后端（LightRAG + RAG-Anything）暴露 REST 接口，本 skill 用 `curl` 调用它们在知识图谱里检索。

- **Base URL**：`http://localhost:8777/api`（可用环境变量 `GRAPHMIND_API_BASE` 覆盖）
- 所有针对图谱的操作都需要一个 `dataset_id`。先确定它。

## 第一步：确定 dataset_id

如果用户没给 `dataset_id`，先列出数据集让用户选，或选唯一/最新一个：

```bash
curl -s http://localhost:8777/api/datasets | jq '.datasets[] | {id, name, entity_count, index_complete}'
```

只用 `index_complete: true` 或 `entity_count > 0` 的数据集——未建好索引的查不出东西。

## 第二步：按需求选接口

| 用户想要 | 接口 |
|----------|------|
| 检索相关上下文（实体/关系/文本块）用于回答问题 | 纯检索 `/search/context` |
| 查某个具体实体的详情和邻居 | 精确实体 `/entity` |
| 查两个实体之间的关系 | 精确关系 `/relationship` |
| 不知道实体全名，模糊找 | 模糊搜实体 `/graph/search-entities` |
| 看某实体周围的子图 | 邻域 `/graph/neighborhood` |

### 纯检索（拿上下文，自己回答）

检索命中的实体/关系/来源，你据此组织答案给用户。

```bash
curl -s -X POST http://localhost:8777/api/datasets/$DS/search/context \
  -H 'Content-Type: application/json' \
  -d '{"query":"示例产品的市场策略","mode":"mix"}' | jq -r .context
```

`mode` 决定检索方式，默认 `mix` 最全面。按问题类型选：

| mode | 适用 |
|------|------|
| `mix` | 通用默认，图谱+向量，综合最佳 |
| `local` | 聚焦某个具体实体的问题（以实体为中心） |
| `global` | 宏观、概括性问题（以关系/主题为中心） |
| `hybrid` | 兼顾细节与全局（local+global，均在图谱内） |
| `naive` | 只要原始文本片段、不用图谱（纯向量 RAG） |

### 精确查实体（需要实体全名）

```bash
curl -s -G http://localhost:8777/api/datasets/$DS/entity \
  --data-urlencode 'name=示例产品®' | jq
```

返回 `{name, properties{entity_type,description,source_id,...}, neighbors[]}`。名字不确定时先用下面的模糊搜。

### 精确查关系（需要两端实体名）

```bash
curl -s -G http://localhost:8777/api/datasets/$DS/relationship \
  --data-urlencode 'source=135#' --data-urlencode 'target=正式准入医院' | jq
```

### 模糊搜实体名

```bash
curl -s -G http://localhost:8777/api/datasets/$DS/graph/search-entities \
  --data-urlencode 'q=产品' --data-urlencode 'limit=20' | jq
```

### 实体邻域子图

```bash
curl -s -G http://localhost:8777/api/datasets/$DS/graph/neighborhood \
  --data-urlencode 'entity=示例产品®' --data-urlencode 'depth=2' | jq '{nodes:(.nodes|length), edges:(.edges|length)}'
```

## 常见流程

用户问“X 和 Y 有什么关系”但不确定全名：先 `search-entities` 找到 X、Y 的准确名，再 `/relationship` 查，或用 `/entity` 看各自邻居。

用户问开放性问题：用 `/search/context`（`mix`）取上下文，你据此组织答案，需要时展示命中的实体/来源溯源。

## 排错

- 连不上：后端没起。提示用户在 GraphMind 目录跑 `./start.sh`（或确认 8777 端口）。
- 答案空/查不到：确认用的是已建索引的数据集（`index_complete: true`）。
- 中文实体名含特殊符号（® # 等）：务必用 `--data-urlencode`，别直接拼进 URL。
