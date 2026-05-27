# 流程画布内置模板

## 注册表（`GET /flows/templates` / 新建流程）

| id | 说明 |
|----|------|
| `blank` | 空白画布（仅创建时用，不出现在「插入模板」） |
| `rag` | 线性 RAG：检索 → 提示词 → LLM |
| `simple_llm` | 用户输入 → LLM → 输出 |

其余节点类型（条件分支、生图/生视频、平台工具等）在编辑页从节点面板拖拽即可，不提供单独内置模板。

## `rag_flow_with_grade.json`

**不在**注册表中展示为可插入模板；使用 ``load_flow_template_graph("rag_with_grade")`` 加载。

## 租户种子

```bash
python cli.py seed flows   # 每租户 2 条【示例】流程：RAG 问答、简单对话
```

## `rag_flow.json` 数据流

见历史文档：input → search → prompt → llm → output；KB 来自 `RunContext.kb_ids` 或节点 `kb_id`。
