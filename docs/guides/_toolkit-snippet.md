# LangChain toolkit（L3 schema 壳）

内置工具的 **function-calling schema** 与租户侧执行分离：

| 层 | 路径 | 职责 |
|----|------|------|
| L3 schema | `miles_integrations/langchain/toolkit/` | `catalog._DECLS` 声明表 + `naming` / `inputs` / `specs`；按 slug 查表，**从不遍历** `_DECLS` |
| 分组集合 | 同文件 `_PLATFORM_SLUGS` / `_OPT_IN_SLUGS` / `_SKILL_SLUGS` / `_GENERATIVE_SLUGS` | 未归组的声明不会出现在任何工具列表（静默） |
| 租户元数据 | `tenant/tools/builtin_registry.py` | 展示名、opt-in、确认策略 |
| 执行 | `tenant/tools/handlers/` | 真正调用（HTTP / 检索 / 生成等） |

新增内置工具：先在 `_DECLS` 加壳并归入某一分组 → registry → handler。双向一致性由 `tests/miles_integrations/langchain/test_toolkit_contract.py` 钉住。更多业务说明见上文 §1–4；AI 栈目录见 [ai-stack.md](./ai-stack.md)。
