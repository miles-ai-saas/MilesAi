# LangChain 接入说明

> 状态：已落地基础层（P6-1）  
> 关联：[agent-enhancement-langchain-stack.md](./agent-enhancement-langchain-stack.md)

## 依赖

```bash
cd backend
pip install -e ".[dev]"   # 已含 langchain-core、langchain-text-splitters
# 可选 OpenAI 适配包
pip install -e ".[agent-stack]"
```

## 模块结构

```
app/ai_stack/langchain/
├── embeddings.py      # PlatformEmbeddings → Sentence-Transformers
├── chat_models.py     # PlatformChatModel → OpenAI 兼容 HTTP
├── vectorstores.py    # search_kb / search_multi_kb → Weaviate
├── rag.py             # retrieve_hits / rag_answer
├── chunking.py        # RecursiveCharacterTextSplitter
└── tools.py           # StructuredTool 定义（内置工具）

app/ai/                # 薄门面，向后兼容
├── embedding.py
├── chunking.py
└── rag.py

app/core/llm_client.py # 委托 ainvoke_chat
```

## 调用链（重构后）

| 业务 | 入口 | LangChain 层 |
|------|------|----------------|
| 智能体 RAG 对话（默认） | `AgentService._rag_chat` | `langgraph.run_rag_workflow`（见 [langgraph-rag-workflow](./langgraph-rag-workflow.md)） |
| 智能体 RAG 对话（legacy） | 同上，`use_langgraph_rag: false` | `rag.rag_answer` |
| 知识库检索 API | `KbService.search` | `vectorstores.search_kb` |
| 流程节点检索 | `rag_nodes.knowledge_search` | `rag.retrieve_hits` |
| 流程 LLM | `llm_nodes.llm_call` | `chat_models.ainvoke_chat` |
| 工具 knowledge_search | `tools.invoke` | `vectorstores.search_kb` |
| 文档入库分片 | `ai.chunking.split_text` | `RecursiveCharacterTextSplitter` |
| 向量化 | `ai.embedding.embed_*` | `PlatformEmbeddings` |

## LangGraph RAG（P6-2）

详见 **[langgraph-rag-workflow.md](./langgraph-rag-workflow.md)**。

智能体绑定知识库且已配置模型时，默认走 `run_rag_workflow()`，不再使用线性 `rag_answer()`。

## 扩展

- 新增内置工具：在 `langchain/tools.py` 增加 `StructuredTool`，并在 `invoke.py` 注册名称。
- 切换 OpenAI 官方客户端：安装 `agent-stack` 后可在 `chat_models.py` 按 `provider` 分支使用 `ChatOpenAI`。
- Redis 缓存：在 `ainvoke_chat` / `embed_query` 外包装 LangChain `Cache`（待做）。
