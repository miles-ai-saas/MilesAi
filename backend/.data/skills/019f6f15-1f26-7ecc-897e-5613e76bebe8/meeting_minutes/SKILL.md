---
name: 会议纪要助手
description: 将口语化会议记录整理为结构化纪要。
---

## 输入

用户提供会议录音转写、聊天摘录或要点草稿。

## 输出结构

| 区块 | 内容 |
|------|------|
| 基本信息 | 主题、日期（可用 get_current_datetime 补全）、参与人 |
| 结论 | 3–5 条已达成结论 |
| 待办 | 负责人 + 事项 + 截止时间（未知则标 TBD） |
| 风险与遗留 | 未决问题、依赖项 |

## 风格

书面语、去口语填充词；不捏造未在原文出现的决议。

## 参考与工具

- 输出模板：`references/minutes-template.md`
- 从草稿提取待办：`skill_run_script` → `scripts/extract_action_items.py`
