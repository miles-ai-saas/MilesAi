# 流程视频参数配方 Implementation Plan

> **归档：** 实施 checklist（2026-08-05）。**现网规格：** [features/flow-orchestration.md](../../features/flow-orchestration.md)；模板见 `backend/app/flow_runtime/templates/video_{t2v,i2v}.json`、前端预设见 `ui/workbench/features/flows/lib/video-generate-presets.ts`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 内置文生/图生视频流程模板 + VideoGenerate 检查器参数预设下拉；未配模型时回退租户默认 video_gen。

**Architecture:** 复用 `FLOW_TEMPLATE_REGISTRY` 与现有画布插入 UX；预设为前端常量；节点运行时对齐 agent 的 `resolve_video_gen_model` 回退。

**Tech Stack:** FastAPI flow_runtime、React flow inspector、pytest。

**Spec:** [docs/superpowers/specs/2026-08-05-flow-video-param-recipes-design.md](../specs/2026-08-05-flow-video-param-recipes-design.md)

## Global Constraints

- Commit message 简体中文 Conventional Commits
- 不新增租户配方实体 / API

---

### Task 1: 后端模板 + 模型回退

- [ ] 新增 `video_t2v.json` / `video_i2v.json`，注册进 registry，更新 README
- [ ] `video_generate`：无 model_config_id 时 resolve 默认，仍无则 BadRequest
- [ ] 扩展模板可编译测试；必要时补节点回退测试
- [ ] `pytest` 相关用例通过
- [ ] Commit：`feat(flows): 新增文生/图生视频画布模板与模型回退`

### Task 2: 前端预设下拉

- [ ] 新增 `video-generate-presets.ts`（或等价）常量
- [ ] `VideoGenerateInspectorForm` 增加配方 select
- [ ] Commit：`feat(flows): VideoGenerate 检查器支持参数配方预设`
