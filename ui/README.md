# MilesAI 前端（Workbench + Admin）

## 代码规范

与仓库根目录 [`.editorconfig`](../.editorconfig) 及 [`prettier.config.mjs`](./prettier.config.mjs) 对齐：

| 项 | 值 |
|----|-----|
| 行宽 | **160** |
| 缩进 | 2 空格（TS/TSX/JS/CSS/JSON） |
| 引号 | 双引号 |
| 分号 | 有 |
| 换行 | LF |

- **格式化**：Prettier（`printWidth: 160`）
- **Lint**：ESLint + `eslint-config-next` + `eslint-config-prettier`（样式冲突以 Prettier 为准）

## 常用命令

先在各应用目录安装依赖（workbench 常用 npm，admin 常用 pnpm）：

```bash
cd ui/workbench && npm install
cd ui/admin && pnpm install   # 或 npm install
```

在 `ui/` 目录可聚合执行（需两侧均已安装依赖）：

```bash
cd ui
npm run format        # 格式化 workbench + admin
npm run format:check
npm run lint
```

单应用（在 `workbench/` 或 `admin/` 下）：

```bash
npm run format
npm run format:check
npm run lint
```
