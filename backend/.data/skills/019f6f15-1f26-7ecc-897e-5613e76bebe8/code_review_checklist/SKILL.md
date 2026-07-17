---
name: 代码审查清单
description: 对 diff 或代码片段做结构化 Review（偏 Web 后端）。
---

## 审查维度

| 级别 | 检查项 |
|------|--------|
| 严重 | 逻辑错误、注入、鉴权缺失、敏感信息硬编码 |
| 建议 | 命名、重复、边界、错误处理、测试缺口 |
| 优点 | 值得保留的实践（如有） |

## 输出

- 按文件/函数定位问题，并给出简短修改建议。
- 区分「必须修复」与「可选优化」。
- 涉及性能估算时可使用 calculator 辅助，但不替代代码阅读。
- 安全项清单见 `references/security-checklist.md`；输出格式见 `references/review-output-format.md`。
- 统计 diff 行数：`skill_run_script` → `scripts/count_diff_stats.py`。
