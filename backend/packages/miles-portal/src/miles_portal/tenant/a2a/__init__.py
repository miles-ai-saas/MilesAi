"""
租户 A2A（Agent-to-Agent）互联。

分层
----
- **登记**：``services.peers`` + ``card_client``（拉取 Agent Card）
- **绑定**：``peer_refs``（CUSTOM 智能体）、``host_bindings``（A2A 宿主）
- **对话**：``invoke`` + ``client``（规则/规划 → JSON-RPC message/send）

与本地 KB：``run_a2a_augmented_chat`` 先 ``_rag_chat`` 再调外部 Peer。
"""
