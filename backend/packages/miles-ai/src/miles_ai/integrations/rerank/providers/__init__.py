"""
Rerank Provider 实现包。

``registry`` import 时注册：
- ``dashscope`` → ``DashScopeRerankProvider``（原生 text-rerank，flat/nested 两种 JSON）
- ``openai_compatible`` → ``OpenAICompatibleRerankProvider``（``POST /reranks``）
"""
