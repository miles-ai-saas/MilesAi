# 后端测试目录

与 [docs/architecture/layering.md](../../docs/architecture/layering.md) §7 对齐，按域分子目录；`conftest.py` 保留在根目录供全局 fixture。

```text
tests/
  conftest.py          # 全局 fixture（api_app、api_client 等）
  api/                 # HTTP / meta / 壳层 smoke
  integration/         # 跨模块编排（编译 + 入库等）
  rag/                 # 解析、分片、检索、向量化
  flow/                # LangGraph 编译、节点、流程 API
  tenant/
    agents/            # 智能体、A2A、对话
    generative/        # 生图 / 生视频任务
    kb/                # 知识库、附件
    tools/             # 工具调用、脚本沙箱
    skills/            # SKILL.md 技能包
    hooks/             # HTTP 钩子、定时任务
  mcp/                 # MCP 客户端与 Runner
  admin/               # 运营后台
  infra/               # 向量库、存储、加解密、日志
  marketplace/         # 应用市场
  media/               # 生成素材与媒体 Provider
```

运行（在 `backend/` 下）：

```bash
pytest -q                    # 全量
pytest tests/rag -q          # 单域
pytest tests/api/test_api_e2e.py -q
```
