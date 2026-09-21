# A2A `tasks/*` 任务寻址的租户边界收口

## 1. 问题

### 1.1 `load_owned_agent_task` 的 docstring 承诺在跨租户时不成立

`services/server.py` 的 `load_owned_agent_task` 是 A2A 对外面**唯一**的「该智能体自己的任务」
寻址点，四个调用点全部经它：`_handle_tasks_get`、`_handle_tasks_cancel`、
`read_task_artifact`、`open_task_subscription`。

它已写下承诺：

> 取「该智能体自己发起」的生成任务；不存在或不属于它一律 `NotFoundError`。
> …回 404 而非 403 —— 不向对端确认任务是否存在。

但函数体先调 `get_generative_job_for_tenant`，租户校验发生在那一层：

```python
job = await get_generative_job_for_tenant(db, ctx, task_id)
if job.source_ref_type != "agent" or job.source_ref_id != agent_id:
    raise NotFoundError("生成任务不存在")
```

`get_generative_job_for_tenant` 先 `db.get` 再 `assert_tenant_access`，而后者对**外租户**资源抛
`ForbiddenError`（HTTP 403）。于是「一律 `NotFoundError`」只对「同租户·跨智能体」成立，
**跨租户时落空** —— 承诺与实际不符，且是四个调用点共有的。

### 1.2 跨租户 id 的四种后果（不统一）

| 调用点 | 现状后果 |
|---|---|
| `_handle_tasks_get` | `ForbiddenError` 逸出 `_dispatch_a2a_rpc` → `handle_a2a_rpc` 的 `except Exception` 记一条流水（`errorCode` 被误标为 `-32603`）→ 重抛 → 全局处理器回 **HTTP 403 + 平台 `{code,message,data}` 信封** |
| `_handle_tasks_cancel` | 同上 |
| `read_task_artifact` | `ForbiddenError` 逸出 → **零审计**（该函数的 `except NotFoundError` 分支不覆盖它）→ HTTP 403 平台信封 |
| `open_task_subscription` | 已收口为 `-32001` + 留痕（2026-09-20 加固提交 `2388ad96`） |

两个后果值得单独点明：

- **协议契约**：本端点对外承诺「协议级错误一律回 HTTP 200 + JSON-RPC 信封，使对端能从正文读到
  失败原因」。拿到平台信封、正文是 `{code,message,data}` 的对端**无从把错误对回自己的 `id`**。
- **存在性 oracle**：`403`（外租户）与 `-32001`（不存在 / 非本智能体）可区分，等于把
  「这个 UUID 在别的租户里存在吗」做成可探测的信号。`403` 还自带
  「无权访问该租户资源」这类内部措辞。

### 1.3 上一批只修了一个调用点，造成同族方法口径分裂

`tasks/resubscribe` 在 `open_task_subscription` 内单独加了 `except ForbiddenError`。这使
**同一个「外租户 id」在三个 JSON-RPC 方法上给出两种结果**：订阅回 `-32001`，另两个回 403 平台信封。
按点修补还会继续留下 `read_task_artifact`（连审计都没有）。

## 2. 已确认的决策

| # | 决策点 | 选定 |
|---|---|---|
| 1 | 收口层次 | **在共用瓶颈 `load_owned_agent_task` 内**把 `ForbiddenError` 收敛为 `NotFoundError`；不逐调用点补 `except` |
| 2 | 上一批的冗余分支 | **删除** `open_task_subscription` 的 `except ForbiddenError`（收口下沉后不可达），避免「同一个不变式两处真相」 |
| 3 | 结构兜底 | **不做** `handle_a2a_rpc` 的「AppError → JSON-RPC 信封」通用兜底；由此产生的残余风险见 §5 |
| 4 | 鉴权层 | **不改**：`UnauthorizedError` / `ForbiddenError("API Key 与目标智能体不匹配")` 属 HTTP 层认证（规范本就用 401/403 表达），继续走平台信封 |

## 3. 设计

### 3.1 收口点

`services/server.py` 的 `load_owned_agent_task`：

```python
try:
    job = await get_generative_job_for_tenant(db, ctx, task_id)
except ForbiddenError:
    # 外租户 id：assert_tenant_access 抛 403。本函数对外承诺「不存在或不属于它一律
    # NotFoundError」，且 A2A 端点的契约是「协议级错误回 JSON-RPC 信封」+「不确认任务
    # 是否存在」—— 403 逸出会同时打破这两条：对端拿到平台信封（无从对回自己的 id），
    # 且 403 与 -32001 可区分，等于给出探测任务是否存在的 oracle。
    # 文案固定，不回显内部措辞。
    raise NotFoundError("生成任务不存在") from None
if job.source_ref_type != "agent" or job.source_ref_id != agent_id:
    raise NotFoundError("生成任务不存在")
```

**这不是新增语义，而是让函数兑现它已有的 docstring 承诺**，同时把该承诺的维护点从「四个调用点」
收敛回「一个函数」。

`from None`：不串联 `ForbiddenError` 的上下文，避免日志/调试器里又出现被刻意抹掉的措辞。

### 3.2 删除冗余分支

`open_task_subscription` 的 `except ForbiddenError`（现 `subscription.py:126-132`）与
`ForbiddenError` 的 import 一并删除 —— 该分支的唯一异常来源（`load_owned_agent_task` →
`get_generative_job_for_tenant` → `assert_tenant_access`）已在瓶颈处转换，留着即为不可达代码。
其注释里那段「403 与 -32001 可区分等于 oracle」的理由**上移到瓶颈**（见 §3.1 注释），不丢失。

删除后 `subscription.py` 的 `try/except` 只剩 `BadRequestError` 与 `NotFoundError` 两个分支。

### 3.3 行为变化矩阵

| 场景 | 现状 | 修复后 |
|---|---|---|
| `tasks/get` 外租户 id | HTTP 403 **平台信封**；审计 `errorCode` 误标 `-32603` | HTTP 200 + JSON-RPC `-32001`；审计 `errorCode` 纠正为 `-32001` |
| `tasks/cancel` 外租户 id | 同上 | 同上 |
| 产物下载 外租户 id | HTTP 403 平台信封 + **零审计** | HTTP 404 平台信封（该端点是普通 HTTP，形状不变）+ 一条 `failed` 流水 |
| `tasks/resubscribe` 外租户 id | `-32001` + 留痕 | **不变**（改由 `NotFoundError` 分支承担） |
| 同租户·跨智能体 | `NotFoundError` / `-32001` | **不变** |
| 超管 API Key 访问外租户 | 放行 | **不变**：`assert_tenant_access` 对 superuser 早退，不会抛 `ForbiddenError`，故转换不触及该路径 |
| 未发布智能体 | `INVALID_PARAMS` | **不变**：该分支在 `load_published_agent`，不经 `load_owned_agent_task` |
| 非法 id（非 UUID / 缺字段） | `INVALID_PARAMS` | **不变**：该分支在 `parse_task_id` |

审计 `errorCode` 由 `-32603` 纠为 `-32001` 是附带收益：`handle_a2a_rpc` 的兜底留痕会对
**未捕获异常**一律按 `INTERNAL_ERROR` 记，而外租户探测被它记成「服务端内部错误」在审计页上
是误报。

### 3.4 测试

| 层次 | 用例 | 断言 |
|---|---|---|
| 瓶颈单元 | `load_owned_agent_task` 遇到 `ForbiddenError` | 抛 `NotFoundError`，且文案不含「租户」（防止把内部措辞回显出去） |
| 调用点 | `tasks/get` 外租户 | 信封 `error.code == TASK_NOT_FOUND`（而非平台信封 / 403） |
| 调用点 | `tasks/cancel` 外租户 | 同上 |
| 调用点 | 产物下载 外租户 | 抛 `NotFoundError` **且**有一条 `failed` 流水（堵「探测不留痕」） |
| API 级 | 注入 `ForbiddenError` 后走**真实** `handle_a2a_rpc` | HTTP **200** + JSON-RPC `-32001` |

API 级那条是必需的：上一批终审的教训是「每环都绿、而组合路径从未跑过」，而本缺陷的可观测面
恰好在「服务层返回信封」与「HTTP 状态码 / Content-Type」之间 —— 服务层单测（直接 `await
handle_a2a_rpc`）看不到状态码。

既有用例 `test_a2a_task_resubscribe.py::test_preflight_rejects_foreign_tenant_task_without_leaking_existence`
**保留不改**：删除订阅层分支后，它由「分支被覆盖」转为**「瓶颈转换被移除」的主判别器**。

### 3.5 文档

`docs/guides/a2a.md` 的任务归属段当前写：

> 任务归属：… 不属于则回 404 / `-32001` 而非 403 —— 不向对端确认任务是否存在。

补一句把**跨租户**也明确纳入（现状该句只在同租户跨智能体意义上成立），并说明产物下载端点是
普通 HTTP、故以 404 状态码表达同一语义。

无需迁移（无模型 / Schema 变更）；无需更新 OpenAPI 快照（视图 docstring 与签名均不变）。

## 4. 为什么选瓶颈而非逐点 / 结构兜底

| 方案 | 取舍 |
|---|---|
| **瓶颈收口（选定）** | 一处改动覆盖四个调用点；`read_task_artifact` 的审计缺口自动补上；承诺的维护点与实现点重合。代价：`load_owned_agent_task` 承担了一层「把下层 403 归一为对外 404」的翻译职责，需在 docstring / 注释写明 |
| 逐调用点补 `except ForbiddenError` | 与上一批做法一致但重复三次；`read_task_artifact` 还要单独记得加 audit；未来新增 `tasks/*` 调用点会再漏一次 |
| `handle_a2a_rpc` 加通用结构兜底 | 能把「协议级错误必经信封」变成结构保证（可覆盖 §5 的残余），但影响面超出本缺陷、且会改变所有未来 `AppError` 的对外表现，本批不做 |

## 5. 明确不做 / 已知残余

1. ~~不做 `handle_a2a_rpc` 的 `AppError` 通用兜底。~~ **已由
   `2026-09-21-a2a-error-sealing-design.md` 关闭**：RPC 层已加兜底，下列两条不再以平台
   信封返回。
   - `_handle_tasks_cancel` 第二个 `try` 里 `cancel_job` 的~~**竞态** `NotFoundError`（job 在
     `load_owned_agent_task` 之后、`cancel_job` 之前被删）~~ **已关闭**：现回 HTTP 200 +
     `-32001`；Redis `publish` 故障仍按非业务异常重抛 500（**未关闭**）。
   - ~~`_handle_message_send` 的 `except Exception` 会把 `ForbiddenError`（如配额超限）
     误标为 `-32603`（不逸出，故不在本批范围）。~~ **已关闭**：现回 `-32602` 并在审计里记
     `errorType`。
2. **不改鉴权层**：`UnauthorizedError`（缺 / 无效 API Key）与
   `ForbiddenError("API Key 与目标智能体不匹配")` 是 HTTP 层认证语义，继续走平台信封与 401/403。
3. **不动 `get_generative_job_for_tenant` 本身**：它是跨功能共用的租户作用域取数，`ForbiddenError`
   对其内部调用方（workbench 页面等）是正确的；归一化只发生在 A2A 对外边界。
4. **不为 `load_owned_agent_task` 引入新的异常类型**：契约要的就是「不确认存在性」，
   `NotFoundError` 已是既有对外语义。
5. **跨租户探测在内部也不再可区分**：收口后，审计 `errorCode` 与 access log 状态码均与「随便编一个 UUID」完全相同（`tasks/get` / `tasks/cancel` 从 403 变 200，产物下载从 403 变 404），`from None` 也让 403 不进日志 —— 我方因此失去了「有人在扫别的租户任务 UUID」的唯一信号。这是「对端不得获得存在性 oracle」的必然代价，本批有意接受。若日后要恢复内部可观测性，需从抛出点把标记一路传到审计写点（`errorCode` 是从最终信封推导的，不是一行改动），单开一单。**本批不改变其状态**：A2A 任务/RPC 面仍无区分信号（`tasks/get` / `tasks/cancel` 的审计 `errorCode` 与 access log 状态码与「随便编一个 UUID」完全相同）；但**产物下载面**的跨租户**附件**失败已因本批的 `errorType=ForbiddenError` / `errorStatus=403`（`services/server.py` 的 `_audit_artifact_failure`）而在审计 `detail` 上可与「随手编的 UUID」区分。

## 6. 验收清单

- [ ] `tasks/get` / `tasks/cancel` 外租户 id 回 HTTP 200 + JSON-RPC `-32001`
- [ ] 产物下载外租户 id 回 404 **且**留下一条 `failed` 流水
- [ ] `tasks/resubscribe` 外租户 id 行为不变（`-32001` + 留痕）
- [ ] 同租户·跨智能体、超管、未发布智能体、非法 id 四条既有路径行为不变
- [ ] `ForbiddenError` 在 `subscription.py` 中不再出现
- [ ] 五道质量门全绿（`pytest` / `ruff check` / `ruff format --check` / `layers-check` / `openapi-check`）
