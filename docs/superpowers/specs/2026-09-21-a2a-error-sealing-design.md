# A2A 对外面错误封口（`AppError` → JSON-RPC 信封）Design

**日期**：2026-09-21
**范围**：`backend/packages/miles-portal/src/miles_portal/tenant/a2a/`、`backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`、文档
**前置**：`2026-09-20-a2a-task-lookup-tenant-boundary-design.md`（任务寻址租户边界收口，已合并 `c070efc7`）

---

## 1. 问题

### 1.1 还剩三处逃逸

上一批把「外租户 id」在任务寻址上的 403 逸出收口了。清点 A2A 对外面的其余错误路径后，还剩三处会让对端拿到**非 JSON-RPC 形状**的响应，或让错误码失真、漏审计：

| # | 位置 | 症状 | 可达性 |
|---|---|---|---|
| **E1** | `a2a/services/server.py::read_task_artifact`（产物下载） | 只捕 `NotFoundError`。同一 `try` 内 `AttachmentService.read_attachment_bytes` 会抛 `BadRequestError("附件文件未就绪")`（`attachment.py:155-156`）、跨租户附件抛 `ForbiddenError`（`attachment.py:183` 的 `assert_tenant_access`）、存储下载故障抛任意异常 —— 三类全部逸出成平台信封**且零审计**，与它自己 docstring 的「成败都留一条审计流水」相矛盾 | 附件上传窗口 / OSS 故障，可达 |
| **E2** | `_handle_tasks_cancel` 第二段 `try` | 只捕 `BadRequestError`。`cancel_job` 先 `get_generative_job_for_tenant` 再取消（`job.py:253`），load 与 cancel 之间任务消失则抛 `NotFoundError`；Redis `publish_generative_job_update`、Celery `revoke`、DB 异常亦可逸出 → `handle_a2a_rpc` 兜底记成 `-32603` 平台信封 | 竞态窄，基础设施故障可达 |
| **E3** | `_handle_message_send` 第二段 | `except Exception` 把所有异常译成 `-32603`。**合规拦截**抛 `BadRequestError("输入内容包含敏感词，已拦截：…")`（`compliance/intercept.py:67`）、配额命中抛 `ForbiddenError` —— 两者都被误标成「服务端内部错误」。指南的审计段**已经如实记录**了这个不一致（`message/send` 侧 `-32603` vs `message/stream` 侧 `rejected`），但当时决定「只如实记录、不改码」 | 合规拦截即可达 |

`tasks/get`、`tasks/resubscribe`（前置与流内）经逐条核查**是干净的**，不在本批范围。

### 1.2 共性：映射没有唯一归属，且有两种失效形态

三处的共性是**「把 `AppError` 译成协议级错误码」这件事没有单一归属**：每个 `_handle_*` 自己记得就映射、忘了就逸出。失效有两种形态，**通用兜底只能治其中一种**：

| 形态 | 例子 | 通用兜底能否修 |
|---|---|---|
| **漏捕**：handler 完全没捕，异常逸出到外层 | **E2** | **能** —— 逸出到 `handle_a2a_rpc` 即被接住 |
| **错捕**：handler 自己捕了，但捕得太窄或映射错了码 | **E1**（捕 1 类、漏 3 类）、**E3**（`except Exception` 把业务异常也吞成 `-32603`） | **兜底本身不能** —— handler 的 `except` 在外层兜底**之前**就截获了异常。E3 只需**停止截获**（一行 `except AppError: raise`）即可让兜底接手；E1 因返回类型不是 JSON-RPC，必须逐点改 |

这一点必须在计划里写清，否则会误以为「加了通用兜底就不用改 E1/E3」。通用兜底的价值是**结构性**的：让「新增方法时漏捕」这一类不再可能；而 E3 说明即使有了兜底，**各 handler 的宽 `except` 仍可能把它挡在门外**，需要逐个确认没有截获。

### 1.3 附带的口径分裂

同一个端点上，未预期异常有两种口径：`message/send` 吞成 `-32603` 信封，而 `handle_a2a_rpc` 的兜底是「审计 `-32603` 后原样重抛」→ HTTP 500 平台信封。二者不可能都对。

---

## 2. 已确认的决策

| 项 | 决策 |
|---|---|
| 收口层次 | 在 `handle_a2a_rpc` 加一层 `AppError` 兜底（逐点 `except` 保留、先行命中，语义不变）；产物下载因返回类型不同，单独在其服务层补宽 `except` + 审计 |
| 码映射 | 见 §3.2 表：404/401/403 在 `tasks/*` 域 → `-32001`，其它域 → `-32602`；400 → `-32602`；其它（含 409）与 5xx → `-32603`。审计额外记原始 `AppError` 类型与 status |
| 未预期异常 | **保持现状**：审计 `-32603` 后原样重抛 → HTTP 500 平台信封。不改口径，只在文档写明这类故障不保证 JSON-RPC 形状 |
| `attachment.py` 不一致 | **改 docstring 说真话**（跨租户抛 `ForbiddenError`，与四个兄弟服务对齐），**不改代码**。「不确认存在性」是 A2A 面的职责，由兜底层把 `ForbiddenError` 压成 404 / `-32001` |

---

## 3. 设计

### 3.1 映射函数与收口点

在 `tenant/a2a/server.py`（纯函数层，已被 API 声明层 import，且已 import `miles_common.exceptions`）新增：

```python
def app_error_envelope(method: str | None, req_id: object, exc: AppError) -> dict:
    """把 ``AppError`` 译成 JSON-RPC 错误信封；A2A 对外面不接受平台信封。"""
```

它只做「取码 + 取文案 + 拼信封」，不碰 DB、不写审计 —— 保持纯函数可单测。

三处 dispatch 各挂一次，**外加两处逐点修复**（§1.2：错捕形态兜底治不了）：

1. **`handle_a2a_rpc`**（覆盖 `message/send` / `tasks/get` / `tasks/cancel`）：在 `_dispatch_a2a_rpc` 外新增 `except AppError as exc:`，位置在现有 `except Exception` **之前**。捕获后：
   - `logger.warning` 记一条（含类型与 status；这是「handler 漏了映射」的信号，值得可查）；
   - `envelope = app_error_envelope(method, req_id, exc)`，**不重抛** —— 于是它继续走到函数尾部那条统一审计，一次调用一条流水的不变式不变。
   - 修 **E2**；对 E1/E3 无效（见 §1.2）。

2. **`_handle_message_send`**（修 **E3** 的截获，映射仍归兜底）：它现有 `except Exception` 会把配额类 `ForbiddenError` 吞成 `-32603`，外层兜底看不到。修法是**不要吞**，在 `except Exception` **之前**插一行让业务异常穿过：

   ```python
       try:
           response = await run_published_agent_chat(db, ctx, agent_id, text, conversation_id=context_id)
       except AppError:
           # 业务异常（配额/权限等）不在此处译码：交给 ``handle_a2a_rpc`` 的统一兜底，
           # 既拿到一致的域映射，也让审计能记下原始 ``errorType``/``errorStatus`` ——
           # 若在这里吞成 -32603，「配额用尽」会被报成「服务端内部错误」。
           raise
       except Exception as exc:
           ... 现状不变 ...
   ```

   **不要**在这里自己拼信封：异常一旦在 handler 内被消费，外层就无法把原始类型写进审计（`_rpc_audit_detail` 的 `origin` 来自捕获到的异常对象）。

   归位于 `handle_a2a_rpc` 尾部那条审计，故 E3 的审计 `errorCode` 会从 `-32603` 变为映射后的码，并带上 `errorType`。

3. **视图 `a2a_jsonrpc`**：三处分流（`message/stream`、`tasks/resubscribe`、`handle_a2a_rpc`）包进 `try/except AppError`，把漏网的译成信封。**说明**：这是纵深防御 —— 两个流式入口当前**无具体可达**的 `AppError` 逸出点（它们的 `try` 只覆盖会在内部消化 `NotFoundError`/`BadRequestError` 的调用，`db.commit()` 抛的是 SQLAlchemy 异常），本批**没有**能反映真实缺陷的 RED 用例；其价值在于未来新增流式方法时自动受保护。用例只能注入式锁定（见 §3.7），不得称其为缺陷回归闸门。

4. **`read_task_artifact`**（修 **E1**，兜底治不了）：不用上面的信封（返回文件流，非 JSON-RPC），见 §3.3。

**全盘确认没有第二个 E3**（`rg "except Exception|except BaseException|except \("` 扫 a2a 层 14 处，逐个定性）：

| 位置 | 定性 | 处置 |
|---|---|---|
| `server.py:238`（`_handle_message_send`） | **E3**，请求路径上吞掉 `AppError` | 本批修（§3.1 第 2 点） |
| `server.py:450`（`handle_a2a_rpc` 兜底） | 审计后原样重抛，业务异常不会走到（`AppError` 分支已在其前） | 保持，但需与新增的 `except AppError` 分支确认顺序 |
| `server.py:233`、`:598`（两个前置校验） | 窄捕获 `(NotFoundError, BadRequestError)` | 保持 |
| `server.py:690`、`:697`、`subscription.py:338` | **流内**（响应头已发出，信封已不可能）：异常存入 `outcome` 或译成终态帧 + 审计 | 保持 —— 属帧协议的错误通道，与本批机制不同 |
| `limits.py:43`、`:65` | 有意 fail-open（限流故障不阻断业务） | 保持 |
| `audit.py:50` | 有意（审计失败绝不影响业务） | 保持 |
| `invoke.py:203` | 出站客户端（平台 → 外部 Agent），非对外面 | 不在范围 |

结论：修掉 `:238` 后，**前置路径上不再有宽 `except` 会吞掉 `AppError`**；流内那几处属于另一种（帧内）错误表达，无需改。

### 3.2 码映射表

```
`exc.status_code in (401, 403, 404)` 且 `method` 以 `"tasks/"` 开头   →  `TASK_NOT_FOUND` (-32001)
`exc.status_code == 400`                                          →  `INVALID_PARAMS` (-32602)
`exc.status_code in (401, 403, 404)` 其它域                        →  `INVALID_PARAMS` (-32602)
其它（含 409）与 5xx                                               →  `INTERNAL_ERROR` (-32603)
```

理由：

- **`tasks/*` 域的 404/403 压成 `-32001`**：延续上一批确立的「对端不得获得存在性 oracle」不变式。跨租户任务若回 `-32602`（参数错）会与「任务不存在」可区分，把上一批修掉的问题从另一条路放回来。
- **400 与其它域的 401/403/404 → `-32602`**：与现有逐点映射一致（`load_published_agent` 的未发布/不存在现行就映射为 `-32602`）。权限问题压成「参数错」对端读不出真实原因，属已知取舍，由审计补偿。
- **`method` 取 `payload["method"]`**：兜底层能拿到；`_handle_message_send` 与视图调用点直接传字面量。

**审计补偿**：`_rpc_audit_detail` 增一个可选关键字 `origin: AppError | None = None`，非空时额外写入 `detail["errorType"]`（类型名）与 `detail["errorStatus"]`（HTTP status）。调用点（`handle_a2a_rpc` 的两个分支）在捕获 `AppError` 时把异常传进去。**只记类型与状态码，不记 `message`** —— `aud_logs` 是租户可见面，`AppError` 文案里可能夹内部 URL 或实现细节。

### 3.3 产物下载层（`read_task_artifact`）

该路由是普通 HTTP 下载（不是 JSON-RPC），限流也已回平台 429，故**统一改用平台信封**，只补两件事：**审计**与**跨租户不确认存在性**。`try` 的 `except` 顺序（子类在前）：

```python
    try:
        job = await load_owned_agent_task(db, ctx, agent_id, task_id)
        if str(attachment_id) not in artifact_ids_from_job_result(job.result):
            raise NotFoundError("附件不是该任务的产物")
        data, mime, filename = await AttachmentService(db, ctx).read_attachment_bytes(attachment_id)
    except NotFoundError:          # 含 load_owned_agent_task 的各种「不存在」
        ... 审计 failed，TASK_NOT_FOUND ...；raise
    except ForbiddenError as exc:  # 跨租户附件：不确认存在性
        ... 审计 failed，TASK_NOT_FOUND + errorType/errorStatus ...
        raise NotFoundError("附件不存在") from None
    except AppError as exc:        # 如「附件文件未就绪」(400)
        ... 审计 failed，INVALID_PARAMS + errorType/errorStatus ...；raise
    except Exception:              # 存储/DB 故障
        ... 审计 failed，INTERNAL_ERROR ...；raise
```

要点：

- **跨租户附件对外 404 而非 403**，与指南「非该任务产物一律 404」同口径。**这属于 A2A 面自己的职责**，`AttachmentService` 不动（§3.5）。
- `except ForbiddenError` 必须排在 `except AppError` 之前（`ForbiddenError` 是 `AppError` 子类）。同理 `NotFoundError` 在最前。
- 在 `except` 块内 `raise` 新异常**不会**被同一 `try` 的其它 `except` 再次捕获，故不会双写审计 —— 这是本段唯一容易写错的地方，需用例钉住「恰好一条流水」。
- 成功路径的审计不变。

### 3.4 未预期异常：保持现状

`handle_a2a_rpc` 现有 `except Exception`（审计 `-32603` + 原样重抛）与 `read_task_artifact` 的新 `except Exception` 都**不改语义**。文档写明：这类故障回 HTTP 500 平台信封，**不保证** JSON-RPC 形状。

### 3.5 `attachment.py` docstring 说真话

`AttachmentService._get_or_raise` 现 docstring：`"""按 ID 取未删附件并校验租户归属；缺失或跨租户均抛 ``NotFoundError``。"""`

但代码后半段是 `assert_tenant_access(self.ctx, att.tenant_id)`，跨租户实际抛 `ForbiddenError`。**这是本仓里唯一一处会撒谎的 `_get_or_raise` docstring** —— 其余兄弟服务（`skills` / `tools` / `prompts` / `models` / `media_assets` / `categories`）要么不写这句话、要么只写「校验租户归属」，**都不做断言，故不存在同类问题**。

改为与代码一致：

```
"""按 ID 取未删附件并校验租户归属；缺失或已删抛 ``NotFoundError``，跨租户抛 ``ForbiddenError``。"""
```

并在其下加一行说明：A2A 对外面会把跨租户压成 404（见 `a2a/services/server.read_task_artifact`），本服务不改这一语义。

**口径**：只求「不说谎」，不追求与兄弟服务措辞统一（它们对此沉默）。

### 3.6 文档

`docs/guides/a2a.md`：

1. 新增「错误与信封」小节（`## 对外暴露` 内），列出 §3.2 的映射表与「协议级错误一律 HTTP 200 + JSON-RPC 信封」的例外（500 不保证形状）。
2. 任务归属段末句「（请求体无法解析、被限流、附件尚未就绪这三类前置失败除外）」改为「（请求体无法解析、被限流这两类前置失败除外）」—— 附件未就绪从此也留痕。
3. 产物下载段补：跨租户附件同样 404，且各类失败（未就绪 / 非本任务产物 / 存储故障）都留痕。
4. `## 审计` 段补：审计 `detail` 在兜底层会多出 `errorType` / `errorStatus`（只记类型与状态码，不记 message）。
5. **改写 `## 审计` 段末尾那段「同一合规拦截在两个方法上 outcome 不一致」**：它说「差异来自 send 侧的错误码映射，本次只如实记录、不改码」—— 本批**正是在改那个码**（合规拦截的 `BadRequestError` 从误标的 `-32603` 变为 `-32602`）。改写为：`outcome` 的差异（`failed` vs `rejected`）来自两个方法各自的判据（send 按信封有无 `error`、stream 按终态帧状态），与错误码无关；并指出 send 侧码已不再是「内部错误」。

`docs/superpowers/specs/2026-09-20-a2a-task-lookup-tenant-boundary-design.md` §5：把残余 #1（`tasks/cancel` 竞态）与 #2（`message/send` 误标 `-32603`）标注为**已由本批关闭**；I2（跨租户探测在内部不再可区分）保持不变。

### 3.7 测试

| 层 | 用例 |
|---|---|
| 纯函数 | `app_error_envelope` 参数化映射表（`tasks/get` 域的 404/403 → `-32001`；其它域 404 → `-32602`；400 → `-32602`；409 → `-32603`；`method=None` 时的归属） |
| `handle_a2a_rpc`（兜底，治漏捕） | **E2 复现**：`tasks/cancel` 里 `cancel_job` 抛 `NotFoundError` → HTTP 200 + `-32001` + 审计 `errorCode == -32001`；另造一个「handler 完全没捕」的 `BadRequestError` → `-32602` + 审计；`RuntimeError` → **仍重抛** + 审计 `-32603`（钉住 §3.4 不变） |
| `_handle_message_send`（治 E3 的截获） | 合规拦截（`BadRequestError`）→ `-32602` 且审计 `errorType == "BadRequestError"`、`errorStatus == 400`；配额类 `ForbiddenError` → `-32602` 且 `errorType == "ForbiddenError"`、`errorStatus == 403`。**判别力点**：去掉新增的 `except AppError: raise` 后两条都应变回 `-32603` 且无 `errorType`（RED 取证） |
| `read_task_artifact`（逐点，治 E1） | `BadRequestError`（附件未就绪）→ 留痕 + 重抛，**恰好一条**；`ForbiddenError` → `NotFoundError("附件不存在")` + 留痕；`RuntimeError` → 留痕 + 重抛；成功路径仍一条 `ok` |
| HTTP 面（`tests/api/test_a2a_server_api.py`） | 产物下载「附件未就绪」→ 400 平台信封 **且有**审计；跨租户附件 → 404 平台信封 **且有**审计；`tasks/cancel` 竞态 → HTTP 200 + `-32001` 信封 |

**判别力要求**：E1/E2/E3 的每条用例都要先 RED。视图层兜底（§3.1 第 3 点）**当前无可达的 `AppError` 逸出点**，故它的用例只能是**注入式机制锁定**（monkeypatch 三个分发点之一抛 `AppError`，断言仍回 JSON-RPC 信封），作用是防止未来重构把这段兜底悄悄删掉；它**不是**缺陷回归闸门，docstring 必须写明「注入式，不代表当前有可达逸出点」。

---

## 4. 为什么选通用兜底而非纯逐点补

只做逐点补（E1 改宽、E2 补 `except NotFoundError`、E3 补 `except AppError`）改动更小、语义更精确，但**不解决 §1.2 的归属问题**：下次新增方法或新增异常类型仍会漏捕。通用兜底让「A2A 对外面不逸出 `AppError`」成为**结构性**保证，逐点映射退化为「更精确的语义」而非「唯一的防线」。

本批的完整构成因此是：**1 处结构兜底（治漏捕）+ 1 行「停止截获」（治 E3）+ 1 处逐点改（治 E1，返回类型不同兜底覆盖不到）+ 1 处纵深防御（视图层，无可证伪用例）**。四者不可互相替代 —— 计划里要按这个分工写，别把 E1/E3 的验收挂在兜底上。E3 尤其要写清楚：兜底**已经**存在与否不是它的修复，**停止让 handler 吞掉业务异常**才是。

代价是码会被压平（权限读不出真实原因），已用审计的 `errorType`/`errorStatus` 补偿。

**不做结构兜底**（中间件/全局 handler 按路径前缀识别 A2A 端点）：那会把「协议形状」知识散到 `miles_core` 的通用层，且无法拿到 `method` 做 `tasks/*` 域判定 —— 域判定必须以请求 payload 为依据，只有 A2A 层拿得到。

---

## 5. 明确不做 / 已知残余

1. **未预期异常仍回 HTTP 500 平台信封**（§3.4）：有意保留 500 的监控语义。对端在 DB/存储故障时拿不到 JSON-RPC 信封，需按 HTTP 状态码兜底处理。已在文档写明。
2. **权限/冲突被压成参数错**：其它域的 401/403/404 → `-32602`，409 → `-32603`，对端读不出真实原因。审计 `errorType`/`errorStatus` 可补偿，但只在租户可见面。若日后需要精确区分，须在 A2A 自定义区间（`-32000..-32099`，已占 `-32000`/`-32001`/`-32002`）新增码并写进指南。
3. **`except Exception` 兜底路径不记 `errorType`**：现行只记 `-32603`，诊断依赖全局处理器的堆栈日志。本批不动（YAGNI）。
4. **`tasks/resubscribe` 的并发上限**：30 分钟长流的并发保护仍是设计级残余（上一批登记），不在本批范围。
5. **跨租户探测在内部不再可区分**：上一批登记的 I2，本批不改变其状态。
6. **合规拦截的文案会带回命中的敏感词**：`BadRequestError(f"输入内容包含敏感词，已拦截：{first.word}")` 的 message 经 `app_error_envelope` 原样发给对端（`message/send` 现状是 `f"智能体执行失败: {exc}"`，**同样包含**）。本批不改这个行为（对端本就是消息发送方），若要脱敏需单开一单。

---

## 6. 验收清单

- [ ] `read_task_artifact` 的 `BadRequestError` / `ForbiddenError` / `Exception` 三条路径都留痕，且各恰好一条
- [ ] 跨租户附件对外 **404**（不是 403），文案 `附件不存在`
- [ ] `tasks/cancel` 竞态 → HTTP 200 + JSON-RPC `-32001`（不再是 500 / `-32603` 平台信封）—— 由**兜底**修复
- [ ] `message/send` 合规拦截（`BadRequestError`）→ `-32602`（不再是 `-32603`），审计记 `errorType` —— 由**「停止截获」+ 兜底**共同修复（兜底单独存在时它仍被 handler 吞掉）
- [ ] `message/send` 配额类 `ForbiddenError` → `-32602`（不再是 `-32603`），审计记 `errorType` —— 同上
- [ ] 非 `AppError` 异常**仍**重抛 → HTTP 500（回归不变）
- [ ] `app_error_envelope` 纯函数映射表逐格有测试
- [ ] `attachment.py` docstring 不再声称跨租户抛 `NotFoundError`（全仓唯一一处撒谎的 `_get_or_raise`；兄弟服务对此沉默，不追求措辞统一）
- [ ] 指南：映射表、留痕例外收窄为两条、产物下载段、审计段（含**改写**那段「合规拦截 outcome 不一致」）
- [ ] 设计 §5 残余 #1/#2 标注为已关闭
- [ ] 五道质量门全绿（`pytest` / `ruff check` / `ruff format --check` / `make layers-check` / `make openapi-check`）
- [ ] 视图层兜底**不**改 `a2a_jsonrpc` 的 docstring → `openapi-check` **不应**漂移；若实施中确需补一句说明，必须同批用 `make openapi-update` 更新快照并在提交说明里点出
- [ ] 视图层兜底有注入式锁定用例（docstring 写明「不代表当前有可达逸出点」）
