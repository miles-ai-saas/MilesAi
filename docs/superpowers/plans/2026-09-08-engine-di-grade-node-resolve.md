# B-2a 实施计划：画布 RelevanceGrade 节点模型解析改走 RunContext.resolve_model 回调

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/grade_nodes.py` 对 `app.tenant.models.services.model_resolve` 的反向 import，使其模型解析改走 B-1 已注入的 `RunContext.resolve_model` 回调。

**Architecture:** 延续 B-1（`llm_nodes.py`）已确立的范式：L1（flow 运行入口）装配 `make_flow_model_resolver` 回调并注入 `RunContext.resolve_model`，节点只调用回调、不再自行查库与解析。本计划将 `relevance_grade` 中 `use_llm_grade` 分支的模型解析迁移到该回调，并补 LLM grade 路径的单元测试。flow 发布对话与 debug-run 两个入口已在 B-1 装配 `resolve_model`（见 `chat_rag.py:90`、`flows/services/flow.py:257`），因此本改动无需触碰装配点。

**Tech Stack:** FastAPI / SQLAlchemy async / LangGraph grading（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`flow_runtime` 禁止 import `tenant`（L1）；允许 `tenant → flow_runtime/integrations` 单向。本计划收敛后，`grade_nodes.py` 不得再出现 `app.tenant.*` import（`flow_runtime` 内 B-1 收尾已满足，此处是最后一个残留）。
- 中文 docstring（README §文档注释）：新增/改动模块须写模块与公开方法 docstring。
- 体量：改动文件不得超过 500 行。
- 语义对齐：LLM 评分仅在 `use_llm_grade=True` 且配置了 `model_config_id` 时触发。模型配置缺失/失效由 `resolve_model` 抛 `BadRequestError`（与 `llm_call` 节点一致）；非 LLM（阈值评分）路径行为零变化。原"模型查不到则静默降级为阈值评分"的语义有意改为显式报错，与 `llm_call` 对齐（`make_flow_model_resolver` 对不存在/禁用的模型抛 `BadRequestError("模型配置不存在或已禁用")`）。
- 测试：本任务跑 `tests/flow/test_relevance_grade_flow.py` + 全量回归（当前 433 基线）不引入失败。
- 提交：单独 commit，message 简体中文，`<type>(<scope>): <简述>`。

---

### Task 1: grade_nodes 模型解析迁移 resolve_model + 补 LLM 路径测试

**Files:**
- Modify: `backend/app/flow_runtime/nodes/grade_nodes.py`
- Test: `backend/tests/flow/test_relevance_grade_flow.py`（追加 2 个用例）

**Interfaces:**
- Consumes: `RunContext.resolve_model: Callable[[str], Awaitable[ModelConfig]] | None`（`flow_runtime/types.py:62`，B-1 已注入）
- Produces:
  - `relevance_grade(node_data, inputs, ctx)` 行为不变；LLM 分支改经 `ctx.resolve_model(str(model_id))`，回调缺失时抛 `BadRequestError`
  - 不再 import `app.tenant.models.services.model_resolve`、`AsyncSessionLocal`、`select`、`ModelConfig`、`UUID`

- [ ] **Step 1: 先读当前文件确认行号**

Run: `cd backend && sed -n '1,70p' app/flow_runtime/nodes/grade_nodes.py`
Expected: 顶部 import 含 `resolve_model_for_invoke`、`AsyncSessionLocal`、`select`、`ModelConfig`、`UUID`；`relevance_grade` 内 `use_llm and model_id` 分支自开会话查 `ModelConfig` 后调 `resolve_model_for_invoke`。

- [ ] **Step 2: 写失败测试（LLM 路径回调解析 + 缺失回调报错）**

在 `backend/tests/flow/test_relevance_grade_flow.py` 顶部 import 区后追加两个测试函数（文件现有 import：`json`、`pytest`、`relevance_grade`、`RunContext`、`validate_graph_for_compile`、`BACKEND_ROOT`；新增 `from app.common.exceptions import BadRequestError` 与 `from app.flow_runtime import nodes` 不需要——直接 `monkeypatch.setattr(grade_nodes, "evaluate_relevance", fake)` 需要 `import app.flow_runtime.nodes.grade_nodes as grade_nodes` 风格。文件当前是 `from app.flow_runtime.nodes.grade_nodes import relevance_grade`，请在该 import 下追加 `import app.flow_runtime.nodes.grade_nodes as grade_nodes_module`）：

```python
import app.flow_runtime.nodes.grade_nodes as grade_nodes_module
from app.common.exceptions import BadRequestError


@pytest.mark.asyncio
async def test_relevance_grade_llm_uses_resolve_model(monkeypatch):
    """LLM 评分：模型经 ctx.resolve_model 解析并传给 evaluate_relevance。"""
    sentinel_model = object()
    captured: dict[str, object] = {}

    async def fake_resolve(model_id: str) -> object:
        captured["model_id"] = model_id
        return sentinel_model

    async def fake_evaluate(hits, *, query, threshold, use_llm_grade, model):
        captured.update(
            hits=hits,
            query=query,
            threshold=threshold,
            use_llm_grade=use_llm_grade,
            model=model,
        )
        return {"relevance": "good", "hits": hits}

    monkeypatch.setattr(grade_nodes_module, "evaluate_relevance", fake_evaluate)

    ctx = RunContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        inputs={"query": "q"},
        resolve_model=fake_resolve,
    )
    hits = [{"content": "a", "score": 0.8}]
    out = await relevance_grade(
        {"relevance_threshold": 0.4, "use_llm_grade": True, "model_config_id": "m-1"},
        {"hits": hits},
        ctx,
    )
    assert captured["model_id"] == "m-1"
    assert captured["use_llm_grade"] is True
    assert captured["model"] is sentinel_model
    assert out == {"relevance": "good", "hits": hits}


@pytest.mark.asyncio
async def test_relevance_grade_llm_missing_resolve_model_raises():
    """LLM 评分但运行上下文缺 resolve_model：显式报错（对齐 llm_call）。"""
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001", inputs={"query": "q"})
    with pytest.raises(BadRequestError):
        await relevance_grade(
            {"use_llm_grade": True, "model_config_id": "m-1"},
            {"hits": [{"content": "a", "score": 0.8}]},
            ctx,
        )
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/flow/test_relevance_grade_flow.py::test_relevance_grade_llm_uses_resolve_model tests/flow/test_relevance_grade_flow.py::test_relevance_grade_llm_missing_resolve_model_raises -q`
Expected: 两个用例 FAIL。第一个因节点仍自开会话查库、不会调 `fake_resolve`（`captured["model_id"]` 缺键 → KeyError/断言失败）；第二个因当前实现静默降级不抛错。

- [ ] **Step 4: 实现——重写 grade_nodes.py**

`backend/app/flow_runtime/nodes/grade_nodes.py` 全文件替换为：

```python
"""画布相关性评分节点（对齐 Agent ``rag_qa.grade_documents``）。

输出 ``relevance`` 为 good / poor / none，compiler 映射为三路条件边 handle。
``use_llm_grade=True`` 时委托 ``integrations.langgraph.grading.llm_grade_relevance``。

模型解析由运行入口注入的 ``RunContext.resolve_model`` 回调完成（同 ``llm_nodes``，
见 ``tenant.flows.services.run_context.make_flow_model_resolver``）；节点不再自行查询。
LLM 评分所需模型缺失或回调缺失时抛 ``BadRequestError``，便于调试与兜底。
"""

from __future__ import annotations

from typing import Any

from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext
from app.integrations.langgraph.grading import evaluate_relevance


async def relevance_grade(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """根据检索 hits 输出 good / poor / none，供三路条件边路由。"""
    hits = inputs.get("hits")
    if hits is None and isinstance(inputs.get("input"), list):
        hits = inputs.get("input")
    if not isinstance(hits, list):
        hits = []

    threshold = float(node_data.get("relevance_threshold", 0.35))
    use_llm = bool(node_data.get("use_llm_grade", False))
    query = str(inputs.get("query") or ctx.inputs.get("query", ""))

    model = None
    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if use_llm and model_id:
        if ctx.resolve_model is None:
            raise BadRequestError("运行上下文未提供模型解析回调")
        model = await ctx.resolve_model(str(model_id))

    result = await evaluate_relevance(
        hits,
        query=query,
        threshold=threshold,
        use_llm_grade=use_llm and model is not None,
        model=model,
    )
    return result
```

要点：删除全部 SQLAlchemy / `resolve_model_for_invoke` / `AsyncSessionLocal` / `UUID` / `ModelConfig` import；新增 `BadRequestError` import；解析逻辑收拢为回调调用。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/flow/test_relevance_grade_flow.py -q`
Expected: 全文件 PASS（含既有 4 个用例与新增 2 个）。

- [ ] **Step 6: 全量回归 + ruff + 残留审计**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/flow_runtime/nodes/grade_nodes.py tests/flow/test_relevance_grade_flow.py`
Expected: 全量 PASS（433 基线）；ruff 无报错。
Run: `cd backend && rg -n "tenant\.models\.services\.model_resolve|tenant\." app/flow_runtime/nodes/grade_nodes.py`
Expected: 无输出（`grade_nodes.py` 已无任何 `app.tenant` import）。
Run: `cd backend && rg -rn "resolve_model_for_invoke" app/flow_runtime`
Expected: 无输出（B-1 + 本任务后 flow_runtime 对 model_resolve 依赖清零）。
（注：`integrations/generative/{image,video,tts}/service.py` 对 `model_resolve` 的引用是**既有残留、属 B-2c 计划范围**，不在本任务验收内；本计划只保证 `grade_nodes.py` 与 `app/flow_runtime` 域清零。）

- [ ] **Step 7: Commit**

```bash
git add backend/app/flow_runtime/nodes/grade_nodes.py backend/tests/flow/test_relevance_grade_flow.py
git commit -m "refactor(flow): RelevanceGrade 节点模型解析改走 resolve_model 回调"
```

---

## Self-Review

**1. Spec coverage:** B-2a 目标（`grade_nodes.py` 消除 `model_resolve` 反依赖）由 Task 1 覆盖：import 清零（Step 4/6 断言）、LLM 路径语义对齐（Step 4 raise）、行为保持（非 LLM 阈值路径不变）、测试补齐（Step 2）、回归（Step 6）。

**2. Placeholder scan:** 无 TBD/TODO；每个 Step 含完整代码或精确命令与预期。

**3. Type consistency:** 用例 1 中 `fake_resolve(model_id: str) -> object` 与 `RunContext.resolve_model: Callable[[str], Awaitable[ModelConfig]]` 的返回兼容（返回 `object` 经 `is` 断言引用相等）；`fake_evaluate` 关键字参数与 `evaluate_relevance(hits, query=..., threshold=..., use_llm_grade=..., model=...)` 一致；模块级 monkeypatch 目标名 `evaluate_relevance` 与文件内顶层 import 一致。RunContext 构造关键字 `resolve_model` 与 `flow_runtime/types.py:62` 一致。
