# Agent 协作说明

## Git Commit

- **语言**：commit message 的 subject 与 body 必须使用**简体中文**。
- **格式**：`<type>(<scope>): <简述>`，说明「为什么」而非罗列文件名。
- **示例**：`refactor(ui): 前端目录迁入 ui/workbench 与 ui/admin`

### Cursor ✨ 生成 commit message

Source Control 的 ✨ 按钮**只读**根目录 [`.cursorrules`](.cursorrules)（不读本文件或 `.cursor/rules/`）。改 commit 语言请编辑 `.cursorrules` 中的 `Commit Message Rules`。

Agent 对话提交时见 [.cursor/rules/commit-messages.mdc](.cursor/rules/commit-messages.mdc)。
