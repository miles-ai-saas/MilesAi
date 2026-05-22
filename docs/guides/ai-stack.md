# AI 栈（LangChain / LangGraph / DeepAgents）

> 类型：实现说明 | 状态：已实现 | 关联：[layering.md](../architecture/layering.md)、[rag-module-migration.md](../architecture/rag-module-migration.md)、[flows.md](./flows.md)

| 层级 | 路径 | 技术 | 职责 |
|------|------|------|------|
| L2 | `app/rag/` | — | Parse / Chunk / Index / Retrieve / Generate |
| L3 | `app/integrations/` | LangChain、LangGraph、LiteLLM、DeepAgents | 模型调用、图编排、工具 |
| L4 | `app/infra/` | DB、S3、向量库客户端 | 外部系统原语 |

分层与依赖规则见 [layering.md](../architecture/layering.md)。**不含** RAG-Anything / MinerU。

## 依赖

```bash
cd backend
pip install -e ".[dev]"
pip install -e ".[agent-stack]"      # 可选：deepagents
pip install -e ".[multimodal]"         # 可选：OCR / Whisper
```

## 目录（当前）

```
app/rag/
├── parse/           # parse_file、PDF/TXT/图/音
├── chunk/           # split_text
├── index/           # upsert_chunk_vector、search_vectors
├── retrieve/        # search_kb_chunks、RRF、PG 关键词
└── generate/        # format_hits_context、rag_answer

app/integrations/    # 新代码请用此包
├── langchain/
│   ├── embeddings.py
│   ├── vectorstores.py   # 调 rag.retrieve.multi_kb
│   └── vector/documents.py
├── langgraph/
├── litellm/
└── deepagents/

app/rag/pipeline/      # run_ingest_pipeline

app/infra/vector_store/
├── factory.py       # get_vector_store()
├── base.py          # Protocol、ChunkVectorRecord
├── weaviate|milvus|pgvector.py
└── documents.py     # LangChain Document 映射（L3/L4 交界）

```

## 调用链

| 业务 | 入口 | 实现 |
|------|------|------|
| 文档入库 | `tenant.kb.ingest` | `rag.parse` → `rag.chunk` → `integrations.langchain.embeddings` → `rag.index` |
| 知识库检索 | `KbService.search` | `rag.retrieve.search_kb_chunks` |
| 智能体 RAG | `AgentService.chat` | `rag.generate` / LangGraph `rag_qa` |
| 流程节点 | `rag_nodes` | `rag.generate.retrieve_hits` |
| 向量库 | `.env` `VECTOR_STORE_BACKEND` | `infra.vector_store.factory.get_vector_store()` |

向量库与入库细节见 [knowledge-base.md](./knowledge-base.md)。

### Embedding（`.env`）

| 变量 | 默认 | 说明 |
|------|------|------|
| `EMBEDDING_BACKEND` | `local` | `local` 或 `litellm` |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-base-zh-v1.5` | 仅 `local` |
| `EMBEDDING_LITELLM_MODEL` | `dashscope/text-embedding-v3` | 仅 `litellm` |
| `EMBEDDING_VECTOR_DIMENSION` | `768` | 新建 KB 维度 |

扩展内置工具：在 `integrations/langchain/tools.py` 增加 `StructuredTool`，并在 `tools/invoke.py` 注册。
