# AI 栈（LangChain / LangGraph / DeepAgents）

> 类型：实现说明 | 状态：已实现 | 关联：[layering.md](../architecture/layering.md)、[flows.md](./flows.md)

| 层级 | 路径 | 技术 | 职责 |
|------|------|------|------|
| L2 | `app/rag/` | — | Parse / Chunk / Index / Retrieve / Generate |
| L3 | `app/integrations/` | LangChain、LangGraph、LiteLLM、DeepAgents | 模型调用、图编排、工具 |
| L4 | `app/infra/` | DB、S3、向量库客户端 | 外部系统原语 |

分层与依赖规则见 [layering.md](../architecture/layering.md)。**不含** RAG-Anything / MinerU。

## 依赖

```bash
cd backend
uv sync --all-packages --group dev    # 安装工作区 10 个包；解析 / 多模态等能力已无条件声明
```

## 目录（当前）

```
app/rag/
├── parse/
│   ├── loaders.py              # 入库主入口：text / pdf / docling / image / audio
│   ├── backends/pypdf.py
│   ├── backends/docling.py
│   ├── image_parser.py / audio_parser.py
│   └── media.py
├── chunk/
│   ├── splitter.py             # chunk_documents、split_text
│   └── types.py                # TextChunk(content, page_no)
├── index/gateway.py
├── retrieve/                   # retriever、hybrid、multi_kb、keyword
├── generate/
├── load/knowledge_bases.py
└── pipeline/ingest.py          # run_ingest_pipeline

app/integrations/
├── langchain/
│   ├── embeddings.py
│   ├── vectorstores.py         # → rag.retrieve.multi_kb
│   └── vector/documents.py
├── langgraph/
├── litellm/
└── deepagents/

app/infra/vector_store/
├── factory.py                  # get_vector_store()
├── base.py
├── weaviate|milvus|pgvector.py # import integrations.langchain.vector.documents
└── __init__.py                 # get_vector_store、Store 实现类
```

## 调用链

| 业务 | 入口 | 实现 |
|------|------|------|
| 文档入库 | `tenant.kb.ingest` | `load_documents_from_bytes` → `chunk_documents` → `embed_texts_for_kb` → `rag.index` |
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
| `EMBEDDING_LITELLM_MODEL` | `dashscope/text-embedding-v4` | 仅 `litellm` |
| `EMBEDDING_VECTOR_DIMENSION` | `768` | 新建 KB 维度 |

扩展内置工具：在 `integrations/langchain/tools.py` 增加 `StructuredTool`，并在 `tools/invoke.py` 注册。
