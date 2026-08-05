# 生视频取消确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `generate_video` 默认不再要求用户确认，对话调用直接入队。

**Architecture:** 仅改内置注册表默认值与文案；调用链已按 `require_confirmation` 分支，无需改 invoke 逻辑。

**Tech Stack:** Python builtin_registry、pytest。

**Spec:** [docs/superpowers/specs/2026-08-05-generate-video-no-confirm-design.md](../specs/2026-08-05-generate-video-no-confirm-design.md)

## Global Constraints

- Commit message 简体中文 Conventional Commits
- 不改生图确认策略、不改其它工具、不改 API 字段

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/tenant/tools/builtin_registry.py` | `generate_video.require_confirmation=False` + description |
| `backend/app/integrations/langchain/tools.py` | docstring |
| `docs/architecture/agent-multimodal-design.md` | 架构文档同步 |
| `backend/tests/tenant/tools/test_tools_confirmation.py` | 断言新默认 |

---

### Task 1: 测试 + 注册表 + 文案

**Steps:**

- [ ] 在 `test_tools_confirmation.py` 增加 `test_builtin_generate_video_requires_no_confirmation`
- [ ] 跑测确认失败（当前为 True）
- [ ] 改 `builtin_registry.py`：`require_confirmation=False`，更新模块注释与 description
- [ ] 改 `tools.py` docstring；改 `agent-multimodal-design.md` 相关句
- [ ] 跑 `pytest tests/tenant/tools/test_tools_confirmation.py -q` 通过
- [ ] Commit：`fix(tools): 生视频默认不再要求确认即可执行`
