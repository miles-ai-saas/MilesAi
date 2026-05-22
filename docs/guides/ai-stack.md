# AI 栈（LangChain / LangGraph / DeepAgents）

> 类型：实现说明 | 状态：已实现 | 关联：[flows.md](./flows.md)、[platform-agents.md](./platform-agents.md)

| 层级 | 技术 | 职责 |
|------|------|------|
| L4 | React Flow + `graph_json` | 可视化编排 |
| L3 | LangGraph | 画布编译、RAG 图、Checkpointer |
| L2 | LangChain | Embedding、检索、分片、工具、模型调用 |
| L1 | DeepAgents | 多子智能体规划与 `task` 委派 |

## 依赖

```bash
cd backend
pip install -e ".[dev]"              # langchain-core、langgraph-checkpoint-redis
pip install -e ".[agent-stack]"      # deepagents、langgraph>=1.2
```

## LangChain 模块

```
app/ai_stack/langchain/
├── embeddings.py    # local：Sentence-Transformers；litellm：云端 embedding
├── chat_models.py   # → LiteLLM acompletion
├── vectorstores.py  # → Weaviate
├── rag.py           # retrieve_hits / rag_answer（legacy）
├── chunking.py
└── tools.py

app/ai/              # 薄门面（embedding、chunking、rag）
app/core/llm_client.py → ainvoke_chat
```

## 调用链

| 业务 | 入口 | 实现 |
|------|------|------|
| 智能体对话（默认） | `AgentService.chat` | RAG Graph / 画布 / DeepAgents / A2A 增强 |
| RAG（默认） | `_rag_chat` | `run_rag_workflow` → [flows.md](./flows.md)#langgraph-rag-对话 |
| RAG（legacy） | `use_langgraph_rag: false` | `rag.rag_answer` |
| 知识库检索 | `KbService.search` | `vectorstores.search_kb` |
| 流程节点 | `rag_nodes` / `llm_nodes` | `retrieve_hits` / `ainvoke_chat` |
| 入库分片 | `ai.chunking` | `RecursiveCharacterTextSplitter` |
| 向量化 | `ai.embedding` | `embed_texts` → `get_embeddings()` |

存储与向量 **配置分层**（部署 env / 租户凭证 / 知识库绑定向量模型）见 [technical-design.md §6.5](../architecture/technical-design.md#65-存储与向量化配置策略)。

### Embedding 配置（`.env`）

| 变量 | 默认 | 说明 |
|------|------|------|
| `EMBEDDING_BACKEND` | `local` | `local` 或 `litellm` |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | 仅 `local` |
| `EMBEDDING_LITELLM_MODEL` | `dashscope/text-embedding-v3` | 仅 `litellm` |
| `EMBEDDING_LITELLM_API_KEY` | 空 | 也可用厂商环境变量（如 `DASHSCOPE_API_KEY`） |
| `EMBEDDING_VECTOR_DIMENSION` | `384` | 新建知识库维度；切到 dashscope v3 时建议 `1024` 并重建索引 |

扩展内置工具：在 `langchain/tools.py` 增加 `StructuredTool`，并在 `tools/invoke.py` 注册。
