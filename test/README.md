# 测试说明

GraphMind 后端 API 测试。多数为**集成测试**，需后端已启动并可访问；图谱/搜索类还需存在一个已完成索引的数据集。

## 运行

```bash
cd backend                                   # 必须在 backend 下，pytest 才能 import app
uv run python -m pytest ../test -v           # 运行全部（不含 e2e）
uv run python -m pytest ../test/test_graph.py -v   # 只跑某个文件
uv run python -m pytest ../test -m e2e -v    # 运行端到端测试（会真实调用 LLM）
```

- 后端地址默认 `http://localhost:8777/api`，可用环境变量 `GRAPHMIND_API_BASE` 覆盖。
- 后端不可达时，依赖它的用例会自动 **skip**（不报错）。
- 没有已索引数据集时，图谱/搜索类用例会自动 **skip**。

## 文件一览

| 文件 | 用途 | 覆盖的接口 |
|------|------|-----------|
| `conftest.py` | 共享 fixtures（`api` 连通性、`indexed_dataset` 复用已索引数据集、`sample_txt/gbk/utf16` 样本文件）与 `e2e` 标记注册 | —（无测试） |
| `test_health_config.py` | 健康检查与配置状态 | `GET /health`、`GET /config/status` |
| `test_datasets.py` | 数据集增删查 | `GET/POST /datasets`、`GET/DELETE /datasets/{id}` |
| `test_documents.py` | 文档上传/列表/删除（含 GBK/UTF-16/大写扩展名/非法类型）。文件按原样保存，不再做编码转换或文本抽取 | `POST/GET /datasets/{id}/documents`、`DELETE /datasets/{id}/documents/{filename}` |
| `test_indexing.py` | 索引启动与状态轮询；`TestIndexingE2E` 为创建→上传→索引→查询的端到端链路（`@pytest.mark.e2e`，默认跳过） | `POST /datasets/{id}/index`、`GET /datasets/{id}/index/status` |
| `test_graph.py` | 图谱数据（limit/类型过滤）、统计、实体分页、关系分页、404 处理 | `GET /datasets/{id}/graph`、`/graph/stats`、`/entities`、`/relationships` |
| `test_search.py` | 非流式问答（basic/local/global/mix 模式、非法 mode 422、404） | `POST /datasets/{id}/search` |
| `test_search_stream.py` | SSE 流式问答：响应头、事件格式与顺序（status→chunk→done）、各模式、错误处理、流式与非流式一致性 | `POST /datasets/{id}/search/stream` |
| `api_test.sh` | 手动冒烟脚本（curl），跑一条主链路：健康→配置→建数据集→上传→索引→轮询→统计。非 pytest，交互式确认是否清理 | 主链路若干接口 |

## 尚未覆盖的接口（TODO）

以下接口目前**没有自动化测试**：

- `POST /api/datasets/{id}/discover-entity-types` — LLM 自动发现实体类型
- `POST /api/config/check-api` — Chat/Embedding 连通性检查
- `GET /api/datasets/{id}/graph/search-entities` — 实体名称模糊搜索
- `GET /api/datasets/{id}/graph/neighborhood` — 实体邻域子图
- `GET /api/datasets/{id}/graph/image` — 多模态实体截图

## 说明

- 迁移到 LightRAG + RAG-Anything 后，原 GraphRAG 的**社区（community）**相关接口已删除，对应测试也已移除。
- 实体分页项字段为 `title/type/description`；关系分页项为 `source/target/description/weight`。
- 搜索 `mode` 校验由 Pydantic pattern 完成，非法值返回 **422**（非 400）。`basic` 是 `naive` 的别名，**响应里会归一化为 `naive`**。
- 文档上传按原样保存（不做编码转换/文本抽取），故 `extracted_chars` 恒为 0、文件名大小写保持原样。原 `_decode_to_utf8` 单元测试已随该功能移除。
- 流式问答会分多个 `chunk` 推送，拼接后等于 `done` 的完整答案；单个 `chunk` 不等于完整答案。
