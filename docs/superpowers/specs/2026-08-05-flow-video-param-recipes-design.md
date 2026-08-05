# 流程视频参数配方 Design

## 1. 背景与目标

智能体 / 流程已支持 `generate_video` / `VideoGenerate`，但缺少可复用的「参数配方」：用户仍需每次手填时长、分辨率等。选定方案：**内置流程模板（文生 + 图生）+ VideoGenerate 检查器轻量预设下拉**。

**目标**

- 创建/插入流程时可选用「文生视频」「图生视频」画布模板，预置常用 duration / resolution。
- 任意流程的 `VideoGenerate` 节点可通过下拉一键写入 duration / resolution。
- 模板不绑死租户模型 UUID；节点未配模型时回退租户默认 `video_gen`。

**非目标**

- 租户自定义配方 CRUD、多镜头分镜、对话侧模板选择器、自动拼接成片。

## 2. 方案概要

### 2.1 内置流程模板

| id | label | 图结构 | 节点预置 |
|----|-------|--------|----------|
| `video_t2v` | 文生视频 | TextInput → VideoGenerate → TextOutput | duration=5, resolution=720P；prompt 空，接上游 |
| `video_i2v` | 图生视频（首帧） | 同上 | 同上；检查器/说明强调需首帧（节点或入边） |

注册：`FLOW_TEMPLATE_REGISTRY`，`insertable=True`。JSON 放 `backend/app/flow_runtime/templates/`。

### 2.2 节点运行时：模型回退

`video_generate`：若 `node_data.model_config_id` 为空，调用现有 `resolve_video_gen_model(..., model_config_id=None)` 取租户默认，不再直接 `BadRequestError`。仍无可用模型时再报错。

### 2.3 检查器轻量预设

`VideoGenerateInspectorForm` 顶部「参数配方」`<select>`：

- 前端常量，例如：`短片 5s·720P`、`稍长 10s·720P`、`高清 5s·1080P`
- `onChange` → `patch({ duration, resolution })`
- 不改 prompt / model / 附件；无后端 API

## 3. 改动清单

| 区域 | 文件 |
|------|------|
| 模板 JSON + registry + README | `backend/app/flow_runtime/templates/` |
| 模型回退 | `backend/app/flow_runtime/nodes/video_generate.py` |
| 预设下拉 | `ui/workbench/features/flows/...`（Inspector + 可选 `lib/video-generate-presets.ts`） |
| 测试 | `test_flow_templates.py` / `test_flow_template_graphs.py`；节点回退单测（若已有模式则跟随） |

## 4. 验证

- `list_flow_templates` 含 `video_t2v` / `video_i2v` 且可编译
- 未配 `model_config_id` 时，有租户默认模型可提交任务；无默认模型时报错信息清晰
- 检查器选预设后 duration/resolution 立即更新

## 5. 风险

- 默认模型与用户预期不一致：检查器仍强制展示模型选择，模板 hint 提示「请确认 video_gen 模型」
- 图生模板未预连图片入边：靠检查器上传或后续自行接线，MVP 可接受
