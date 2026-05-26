# 流程编排 — 生成类多模态技术设计（生图 / 生视频 / 语音）

**日期：** 2026-05-26  
**状态：** 设计稿（未实施）  
**关联：** [flow-llm-multimodal-design.md](./flow-llm-multimodal-design.md)（识图输入）、[flow-orchestration-enhancement.md](./flow-orchestration-enhancement.md)、[model-providers.md](../guides/model-providers.md)、[flows.md](../guides/flows.md)

---

## 1. 文档定位与能力矩阵

MilesAI 中与「多模态」相关的能力应拆成 **三条独立技术线**，勿混在同一方案里：

| 技术线 | 产品说法 | API 形态 | 流程编排 | 文档 |
|--------|----------|----------|----------|------|
| **A. 对话生文** | 生文、RAG 回答 | Chat Completions | ✅ `LLMCall` 已支持 | [flows.md](../guides/flows.md) |
| **B. 理解型输入** | 识图问答 | Chat + `image_url` part | ❌ 设计稿 | [flow-llm-multimodal-design.md](./flow-llm-multimodal-design.md) |
| **C. 生成型输出** | 生图、生视频、TTS 等 | Images / Video Task / Speech API | ❌ **本文档** | 本文 |

**本文（C）** 定义：如何在 **流程画布** 中调用 `model_type ∈ { image_gen, video_gen, tts, … }`，将 **生成物**（图片/视频/音频文件）写入对象存储并以 **附件 / URL** 交给下游节点（如 `TextOutput` 展示链接）。

---

## 2. 现状（As-Is）

### 2.1 模型目录

`ModelCapabilityType` 已包含：

| `model_type` | 说明 | 种子示例 |
|--------------|------|----------|
| `llm` / `reasoning` | 生文 | DeepSeek、通义 Plus 等 |
| `vision` | 图像理解 | 通义 VL、豆包视觉 |
| `image_gen` | 文生图 / 图生图 | 豆包 Seedream、万相 t2i |
| `video_gen` | 文生视频 / 图生视频 / 数字人 | 万相 i2v、s2v |
| `asr` / `tts` | 语音识别 / 合成 | Paraformer、CosyVoice |
| `embedding` / `rerank` | RAG 能力 | 非生成类，不走本方案 |

租户可在 **模型供应商** 页看到上述卡片；内置种子见 `scripts/seed/model_catalog.py`。

### 2.2 运行时

| 路径 | 行为 |
|------|------|
| `integrations.litellm.adapter.litellm_chat_completion` | 仅允许 `llm \| reasoning \| vision`；对 `image_gen` 调用返回 **400**（见 `test_litellm_adapter`） |
| `flow_runtime.nodes.llm_nodes` | 仅文本 Chat，无生成 API |
| 画布节点 | 无 `ImageGenerate` / `VideoGenerate` 等类型 |
| `task_records` + Celery | 已用于 **文档入库** 等；可复用模式做 **异步生视频** |

### 2.3 与知识库入库

| 能力 | 模块 | 说明 |
|------|------|------|
| 图/音 → **文本** 再检索 | `rag/parse` + `[multimodal]` | 入库侧 OCR/Whisper，**不是**生图生视频 |
| 文 → **图/视频** 文件 | 无 | 本方案目标 |

---

## 3. 目标与非目标

### 3.1 目标（To-Be）

1. **生图（image_gen）**：画布节点 `ImageGenerate`，输入 prompt（+ 可选参考图），输出 **`attachment_id`**（元数据）；预览/下载走鉴权内容 API，**非** 签名 URL。
2. **生视频（video_gen）**：画布节点 `VideoGenerate`，支持 **异步任务**（提交 → 轮询/回调 → 产出视频附件）；同步 run 可返回 `task_id` 或阻塞等待（可配置超时）。
3. **与流程串联**：上游 `LLMCall` 生成 prompt → 边传入 `ImageGenerate`；生成结果 → `TextOutput` / 下游 `LLMCall`（描述成片）。
4. **模型统一**：继续用 `ModelConfig` + BYOK；按 `model_type` 路由到 `integrations/generative/` 下各 Provider。
5. **可观测**：写入 `task_records`（类型如 `flow.image_gen` / `flow.video_gen`）与节点 `steps` 元数据。

### 3.2 非目标（v1）

| 项 | 说明 |
|----|------|
| 在 `LLMCall` 内「顺便生图」 | 生成走 **独立节点** + 独立集成层，不扩展 chat completion |
| 画布 **流式** 预览生成进度 | v1 仅 steps 状态 + 任务 API 查询；SSE 列为 v2 |
| 运营端 **训练/微调** 模型 | 仍用厂商 API |
| 生成物 **自动入库 KB** | **不做默认**；可选「升格入库」见 [media-assets-design.md](./media-assets-design.md) |
| 全厂商 **统一抽象** 到 100% 相同参数 | 允许 `ModelConfig.extra` 承载厂商差异（与 embedding 相同思路） |

### 3.3 与「识图」方案关系

- [flow-llm-multimodal-design.md](./flow-llm-multimodal-design.md)：**输入** 多模态（vision）。  
- 本文：**输出** 多模态（image_gen / video_gen）。  
- 可组合：`TextInput` + 附图 → `LLMCall(vision)` 写脚本 → `VideoGenerate` 成片（Phase 4 示例链）。

---

## 4. 架构原则

### 4.1 分层

```text
flow_runtime.nodes.image_generate / video_generate
  → integrations.generative.registry（按 model_type + invoke_mode）
    → providers/dashscope_wan.py | doubao_seedream.py | openai_images.py | ...
      → httpx / 厂商 SDK
        → infra.storage.upload_bytes → sys_attachments
```

- **L2 流程**（`flow_runtime`）：节点 handler、输入输出契约、写 `RunContext` / steps。  
- **L3 集成**（`integrations/generative`）：厂商 API、轮询、错误映射。  
- **L1 租户**（`tenant/flows`）：run API、合规、Hook、配额（后续）。

**禁止** 在 `tenant/flows/services` 内直接 `httpx.post` 厂商 URL。

### 4.2 新节点须满足三处一致

| 层 | 路径 |
|----|------|
| Handler | `flow_runtime/nodes/registry.py` |
| 编译 | `integrations/langgraph/compiler`（`CANVAS_NODE_TYPES`） |
| 前端 | `frontend/lib/flow-nodes.ts`、`flow-node-schemas.ts`、`FlowNodeInspector` |

### 4.3 输出契约（统一）

生成节点 **统一输出** 结构，便于下游解析：

```json
{
  "kind": "image",
  "attachment_id": "019e…. ",
  "mime_type": "image/png",
  "width": 1024,
  "height": 1024,
  "provider_task_id": "optional-vendor-id"
}
```

视频增加 `duration_sec`、`cover_attachment_id`（可选）。  
`TextOutput` 与 `compiler._gather_node_inputs` 对 `output` 为 dict 时：展示 `attachment_id` 或 markdown 链接（前端经鉴权 API 取内容渲染，见 [multimodal-roadmap.md](./multimodal-roadmap.md) §2.1）。

---

## 5. 集成层设计（`integrations/generative`）

### 5.1 目录结构（建议）

```text
backend/app/integrations/generative/
  __init__.py
  constants.py          # EXTRA_* 键、默认尺寸、轮询间隔
  types.py                # GenerateImageRequest/Result, GenerateVideoRequest/Result
  registry.py             # register_provider(model_type, invoke_mode, Provider)
  image/
    service.py              # generate_image_for_model(model, request) -> Result
    providers/
      dashscope_wan.py      # 万相 t2i 异步
      doubao_seedream.py
      openai_compatible.py  # DALL·E 形状网关
  video/
    service.py
    providers/
      dashscope_wan.py      # i2v / s2v 异步 task
  speech/                 # Phase 3：tts / asr（可选）
    ...
```

### 5.2 `invoke_mode` 与 `ModelConfig.extra`

沿用 [model-config-extra.md](../guides/model-config-extra.md) 思路，**生成类** 单独常量文件 `integrations/generative/constants.py`：

| 键 | 适用 | 说明 |
|----|------|------|
| `invoke_mode` | 共用 | 如 `dashscope_wan`、`doubao_volc`、`openai_images` |
| `image_size` | image_gen | `1024x1024`、`16:9` 等（厂商映射表） |
| `image_style` | image_gen | 可选风格 preset |
| `video_duration` | video_gen | 秒数上限 |
| `video_aspect_ratio` | video_gen | `16:9` / `9:16` |
| `poll_interval_sec` | 异步 | 默认 2 |
| `poll_timeout_sec` | 异步 | 默认 600 |

创建/更新 `ModelConfig` 时：`tenant/models/services/model.py` 按 `model_type` 校验 `invoke_mode ∈ known_*_modes()`。

### 5.3 Provider 协议（示意）

```python
class ImageGenerateProvider(Protocol):
    async def generate(
        self,
        model: ModelConfig,
        *,
        prompt: str,
        negative_prompt: str | None,
        reference_image_url: str | None,  # 图生图 / i2i
        size: str,
        n: int,
    ) -> ImageGenerateResult: ...

class VideoGenerateProvider(Protocol):
    async def submit(
        self,
        model: ModelConfig,
        *,
        prompt: str,
        image_url: str | None,   # 图生视频
        audio_url: str | None,   # 数字人 s2v
        duration: int,
    ) -> str: ...  # vendor_task_id

    async def poll(
        self,
        model: ModelConfig,
        vendor_task_id: str,
    ) -> VideoGenerateResult | None: ...  # None = still running
```

同步生图：Provider 内部一次 HTTP 返回 bytes。  
异步生视频：Provider `submit` + `poll`；节点 handler 内 **asyncio 轮询** 或委托 Celery（见 §6.2）。

### 5.4 与 LiteLLM 的关系

| 能力 | 是否走 LiteLLM |
|------|----------------|
| 生文 / vision | ✅ `litellm.acompletion` |
| 生图 / 生视频 | ❌ v1 **直连厂商**（LiteLLM 对部分 image API 支持有限且与 chat 混用易混淆） |

后续若 LiteLLM 某版本统一 `aimage_generation`，可增 `invoke_mode=litellm` 作为可选 Provider，不阻塞 v1。

---

## 6. 画布节点设计

### 6.1 `ImageGenerate`（生图）

| 字段 | 类型 | 说明 |
|------|------|------|
| `model_config_id` | uuid | 必填，`model_type=image_gen` |
| `prompt_from` | enum | `input` \| `node_data`（固定 prompt） |
| `prompt` | string? | `node_data` 时使用 |
| `negative_prompt` | string? | |
| `reference_image_from` | handle? | 可选：`input` 接收上游附图 URL/attachment |
| `size` | string | 默认 `1024x1024`，可被 model.extra 覆盖 |
| `n` | int | 默认 1，v1 建议 max 4 |
| `label` | string | 生图 |

**Handles：** in `prompt`（或 `input`）、可选 `reference` · out `output`（§4.3 结构）

**执行：**

1. 解析 prompt 字符串。  
2. `resolve_model_for_invoke` + `generate_image_for_model`。  
3. 上传对象存储，创建 `sys_attachments`（`purpose=flow_generated`）。  
4. 返回 output dict。

### 6.2 `VideoGenerate`（生视频）

| 字段 | 类型 | 说明 |
|------|------|------|
| `model_config_id` | uuid | `model_type=video_gen` |
| `mode` | enum | `text_to_video` \| `image_to_video` \| `digital_human`（映射厂商） |
| `prompt` / `image` / `audio` | 来源同生图 | 按 mode 必填项校验 |
| `duration` | int | 秒 |
| `wait_until_done` | bool | 默认 true（调试）；false 时只返回 `task_id` |
| `poll_timeout_sec` | int | 默认 600 |

**异步策略（二选一，Phase 1 推荐 A）：**

| 策略 | 说明 | 适用 |
|------|------|------|
| **A. 节点内轮询** | `run` 阻塞至完成或超时 | 工作台调试、短视频 |
| **B. Celery 子任务** | `run` 立即返回 `task_id`；前端轮询 `GET /tasks/{id}` | 长视频、生产 |

Phase 1 可用 **A** 降低改动面；Phase 2 引入 **B** 与 `task_records` 统一。

### 6.3 `TextToSpeech` / `SpeechToText`（可选 Phase 3）

| 节点 | model_type | 输出 |
|------|------------|------|
| `TextToSpeech` | `tts` | 音频 attachment |
| `SpeechToText` | `asr` | 文本 → 接 `PromptTemplate` |

与流程AI链组合：音频入口 → ASR → RAG → LLM。

### 6.4 示例画布（Phase 4 参考）

```text
TextInput → LLMCall → ImageGenerate → TextOutput
                ↓ prompt
TextInput → ImageGenerate(参考图) → VideoGenerate → TextOutput
```

---

## 7. API 与运行时

### 7.1 `RunContext` 扩展（可选）

```python
generate_options: dict[str, Any] = field(default_factory=dict)
# 例如：{ "poll_timeout_sec": 300, "store_to_kb_id": null }
```

大部分参数落在 **节点 data**；run 级仅保留全局超时。

### 7.2 `POST /flows/{id}/run` 响应

同步生图完成时与今日相同：`output` + `steps`。

异步视频（策略 B）时扩展：

```json
{
  "output": null,
  "steps": [...],
  "async_task_id": "celery-uuid",
  "status": "running"
}
```

前端调试面板增加「生成任务」Tab，轮询 `GET /tasks/{id}`。

### 7.3 附件与权限

- 生成文件：`purpose=flow_generated`（常量 `tenant/flows/constants.py`）。  
- `resource_type=flow`，`resource_id=flow_id`。  
- 租户隔离与附件读写复用 `AttachmentService`；对外 **不** 默认提供对象存储签名 URL。

### 7.4 配额与合规（Phase 2）

| 项 | 说明 |
|----|------|
| 配额 | 按租户限制 日/月 生成次数、总像素数 |
| 合规 | `check_input` 扫描 prompt；生成结果可选异步审核（非 v1） |
| Hook | `before_tool` 形态可复用为 `before_generate`（后续） |

---

## 8. 前端

### 8.1 调色板

| 节点 | 分组 | 图标 |
|------|------|------|
| `ImageGenerate` | 生成 | 图片 |
| `VideoGenerate` | 生成 | 视频 |

模型下拉 **仅** `model_type` 匹配项；无模型时引导至模型供应商页配置 Key。

### 8.2 属性面板

- 生图：模型、尺寸、固定/上游 prompt、参考图 handle 说明。  
- 生视频：模式、时长、是否等待完成、超时。

### 8.3 调试面板

- 展示生成物缩略图/视频播放器（`attachment_id` + 鉴权内容 API 或上传阶段本地预览）。  
- `steps` 中显示 `provider_task_id`、耗时、失败原因。

### 8.4 智能体入口（Phase 3）

- Agent 工具 `generate_image` / `generate_video` 封装同一 `integrations.generative` 服务。  
- 与画布节点共享 Provider，避免双实现。

---

## 9. 分阶段交付

### Phase 0 — 本文档 + 集成骨架

- `integrations/generative` 包、`registry`、常量。  
- `model.py` 创建 `image_gen` / `video_gen` 时校验 `invoke_mode`。  
- 单测：registry 路由；mock Provider。

### Phase 1 — 生图（同步）

| 项 | 交付 |
|----|------|
| Provider | 至少 1 个厂商（建议通义万相 t2i 或豆包 Seedream） |
| 节点 | `ImageGenerate` + registry + compiler + 前端检查器 |
| 存储 | 生成图 → attachment |
| 测试 | 集成测试 mock HTTP |

### Phase 2 — 生视频（异步）

| 项 | 交付 |
|----|------|
| Provider | 万相 i2v 或同类 submit/poll |
| 节点 | `VideoGenerate`；节点内轮询或 Celery |
| 任务 | `task_records` 关联 `flow_run_id`（可选） |
| 前端 | 等待 UI + 失败重试 |

### Phase 3 — 语音 + Agent 工具

- `TextToSpeech` / `SpeechToText` 节点（按需）。  
- Agent 侧 `generate_image` / `generate_video` 工具与 `ChatResponse.artifacts`（见 [agent-multimodal-design.md](./agent-multimodal-design.md) §5）。

### Phase 4 — 编排体验

- 模板：文生图、文案→分镜→视频。  
- 与 [flow-llm-multimodal-design.md](./flow-llm-multimodal-design.md) 联调：识图 + 生图链。

---

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| 厂商 API 差异大 | `invoke_mode` + Provider 隔离；extra 文档化 |
| 生视频耗时长阻塞 worker | 超时 + Celery；`wait_until_done=false` |
| 生成内容合规 | prompt 合规扫描；运营可下架模型 |
| 费用失控 | 配额 + 单次 run 限制张数/秒数 |
| 大图占存储 | 生命周期策略；租户级清理任务 |

---

## 11. 测试计划

| 类型 | 用例 |
|------|------|
| 单元 | Provider payload 构建、尺寸映射 |
| 单元 | `ImageGenerate` handler：prompt 解析、输出 schema |
| 集成 | mock 厂商 → 对象存储 → attachment 可查 |
| 集成 | 视频 poll 超时 / 成功路径 |
| 回归 | 原 RAG 模板无生成节点时行为不变 |
| E2E | 工作台：选 image_gen 模型 → run → 预览图 |

---

## 12. 代码入口（实施时）

| 模块 | 路径 |
|------|------|
| 生图节点 | `backend/app/flow_runtime/nodes/image_nodes.py`（新建） |
| 生视频节点 | `backend/app/flow_runtime/nodes/video_nodes.py`（新建） |
| 注册表 | `backend/app/flow_runtime/nodes/registry.py` |
| 集成层 | `backend/app/integrations/generative/` |
| 模型校验 | `backend/app/tenant/models/services/model.py` |
| 附件 | `backend/app/tenant/attachments/services/attachment.py` |
| 任务 | `backend/app/tenant/tasks/services/task.py`、`workers/tasks/` |
| 流程 run | `backend/app/tenant/flows/services/flow.py` |
| 种子模型 | `backend/scripts/seed/model_catalog.py` |

---

## 13. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-26 | 初版：生文/识图/生图/生视频边界、集成层、画布节点、分阶段 |
