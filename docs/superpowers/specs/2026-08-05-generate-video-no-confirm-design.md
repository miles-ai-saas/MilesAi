# 生视频工具取消确认 Design

## 1. 背景与目标

智能体开启生视频后，模型调用 `generate_video` 会因内置工具 `require_confirmation=True` 中断，助手回复要求用户点「确认执行」。工作台场景下，用户已主动选用生视频能力，二次确认多余。

**目标：** 对话中调用 `generate_video` 直接入队执行，不再弹出确认。

**非目标：**

- 不做智能体级「是否需确认」开关
- 不改确认条 UI / `pending_tool` API 字段（其它工具仍可用）
- 不改生图确认策略（`n≥2` 仍可触发确认）
- 不取消进行中任务的取消能力

## 2. 方案

将内置注册表中 `generate_video.require_confirmation` 改为 `False`。

调用链 `invoke_tool_with_context` 已根据 `meta["require_confirmation"]` 决定是否抛 `ToolConfirmationRequired`；改默认后对话路径自然直通，前端确认按钮不再出现。

## 3. 行为

| 场景 | 变更后 |
|------|--------|
| 对话调用 `generate_video` | 直接执行 / 入队，返回 artifacts / generative_jobs |
| 用户取消进行中任务 | 不变（现有进度条取消） |
| `generate_image` 且 `n≥2` | 仍可要求确认 |
| 其它 `require_confirmation=True` 工具 | 不变 |

## 4. 改动清单

1. `backend/app/tenant/tools/builtin_registry.py`：`generate_video.require_confirmation = False`；更新模块注释与工具 `description`（去掉「调用前需确认」）。
2. `backend/app/integrations/langchain/tools.py`：`_make_generate_video_tool` 文档字符串去掉「常需用户确认」。
3. `docs/architecture/agent-multimodal-design.md`：同步「默认确认」表述。
4. 测试：断言 `get_builtin("generate_video")["require_confirmation"] is False`（可放在既有 `test_tools_confirmation.py`）。

说明：`scripts/seed/tools.py` 中的确认项为其它工具，与本变更无关（builtin 以代码注册表为准，不依赖 seed 覆盖 `generate_video`）。

## 5. 验证

- 单测：`generate_video` 默认不要求确认。
- 手动：启用生视频的智能体发送「生成跳舞视频」→ 直接出现排队/进度，无「确认执行」。

## 6. 风险

费用与耗时仍由用户主动对话触发；误触成本通过「取消任务」与配额/模型配置约束，不靠二次确认。
