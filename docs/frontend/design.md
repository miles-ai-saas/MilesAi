# MilesAi 前端设计规范

> 适用范围：`ui/workbench/`（租户 AI 工作台 + 组织设置）、`ui/admin/`（平台运营后台）  
> 技术栈：Next.js 14 · Tailwind CSS 3 · 组件级 CSS（`globals.css`）  
> 品牌主色与公司 Logo「行千里」保持一致。

---

## 1. 品牌层级

| 层级 | 名称 | 用途 |
|------|------|------|
| 公司品牌 | **行千里** | Logo 主文案；侧栏/顶栏仅展示一次（`CompanyLogo` compact） |
| 产品品牌 | **MilesAi** | 产品线副标题、页面 title、API `APP_NAME` |
| 英文标语 | **NO STEP NO MILE** | 仅完整 Logo（登录 Hero、`variant="full"`） |

**原则**

- 导航区（顶栏、侧栏）：**一行「行千里」+ 一行产品线**（如 `MilesAi · 工作台`），不叠加图标 mark 与文字重复。
- 登录/marketing 区：可用 `CompanyLogo` `full`（含英文标语）。
- Favicon / 小图标：`/brand/logo-mark.svg`（「千里」字标）。

---

## 2. 色彩系统

### 2.1 公司色（Logo 源色）

| Token | 色值 | 说明 |
|-------|------|------|
| `company.orange` | `#E66432` | Logo「行千里」主色 |
| `company.tagline` | `#C9A88E` | Logo 英文标语 |

常量定义：`ui/workbench/components/brand/company-logo.tsx`（`COMPANY_ORANGE` / `COMPANY_TAGLINE`）。

### 2.2 产品主色（Tailwind `brand`）

与 `company.orange` 对齐，用于交互、强调、导航选中态。

| Token | 色值 | CSS 变量 | 用途 |
|-------|------|----------|------|
| `brand` | `#E66432` | `--brand` | 主按钮、链接强调、选中导航 |
| `brand-light` | `#FEF3EE` | `--brand-light` | 选中背景、浅色块、登录渐变底 |
| `brand-soft` | `#F9D4C4` | `--brand-soft` | 装饰图形、次要高亮 |
| `brand-dark` | `#C45228` | — | 主按钮 hover、深色强调 |
| `brand-foreground` | `#FFFFFF` | — | 主按钮文字 |

### 2.3 中性色

| Token | 色值 | 用途 |
|-------|------|------|
| `surface` | `#FFFFFF` | 卡片、顶栏、侧栏背景 |
| `surface-muted` | `#F5F5F5` | 页面底色 |
| `surface-subtle` | `#FAFAFA` | 可选浅背景 |
| `ink` | `#404040` | 正文 |
| `ink-muted` | `#737373` | 次要文案、导航默认 |
| `ink-faint` | `#A3A3A3` | 分组标题、占位符 |
| `line` | `#E5E5E5` | 边框、分割线 |
| `line-soft` | `#F0F0F0` | 卡片内部分割 |

### 2.4 阴影与圆角

| Token | 值 |
|-------|-----|
| `shadow-card` | `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(230,100,50,0.06)` |
| `shadow-panel` | `0 4px 24px rgba(0,0,0,0.06)` |
| `rounded-xl` | `0.75rem`（卡片、导航项） |
| `rounded-2xl` | `1rem`（大块面板） |

### 2.5 使用约束

- **禁止** 在 UI 中引入与 `brand` 无关的高饱和强调色（如旧版玫红 `#e11d48`）。
- 状态色（成功/警告/错误）暂未单独 token 化；新增时请在本规范附录扩展，避免硬编码散落。
- 深色模式：当前未启用；若后续支持，须在 `:root` 与 `tailwind.config` 同步维护两套 token。

**配置来源**

| 文件 | 说明 |
|------|------|
| `ui/workbench/tailwind.config.ts` | Tailwind 扩展色、阴影 |
| `ui/workbench/app/globals.css` | CSS 变量 + 组件类 |
| `ui/admin/tailwind.config.ts` | 与租户端保持一致 |
| `ui/admin/app/globals.css` | 同上 |

---

## 3. 字体与排版

### 3.1 字体栈

两端通过 `lib/fonts.ts` 加载 **Noto Sans SC**（`next/font/google`，字重 **400 / 500 / 600 / 700**），CSS 变量 `--font-sans`；Tailwind `font-sans` 定义在 `lib/font-family.ts`（勿在 Tailwind 配置中直接 import `fonts.ts`）。

```css
/* body（globals.css）与 theme.extend.fontFamily.sans 一致 */
var(--font-sans), "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, -apple-system, sans-serif
```

| 项 | 说明 |
|----|------|
| 根布局 | `<html className={appFont.variable}>` + `<body className="{appFont.className} font-sans antialiased">` |
| 渲染 | `-webkit-font-smoothing: antialiased`、`-moz-osx-font-smoothing: grayscale`、`text-rendering: optimizeLegibility` |
| Logo 中文 | `PingFang SC`, `Noto Sans SC`, `Microsoft YaHei`（SVG 内嵌） |
| Logo 英文标语 | `Segoe UI`, `Helvetica Neue`, `system-ui`（与 UI 西文栈一致，**不**单独引入 Inter） |
| 等宽场景 | 表单 `model_code`、任务 ID 等沿用浏览器默认 `font-mono`，无单独 Web 字体 |

### 3.2 字号层级（常用）

| 场景 | 类名 / 尺寸 |
|------|-------------|
| 页面主标题 | `text-3xl` / `text-4xl` `font-bold` |
| 卡片标题 | `text-xl` `font-semibold` |
| 正文 | `text-sm` / `text-base` |
| 侧栏分组 | `text-[11px]` `uppercase` `tracking-wider` `text-ink-faint` |
| 产品线副标 | `text-[11px]` `font-medium` `text-ink-muted` |

### 3.3 行高与字重

- 正文：`leading-relaxed`（营销文案）。
- 导航选中：`font-medium`。
- 按钮：`font-medium`（`text-sm`）。

### 3.4 等宽字体（代码 / ID / 技术字段）

不单独引入 Web 等宽字体，统一使用 Tailwind **`font-mono`**（系统默认等宽栈，如 SF Mono / Menlo / Consolas）。

| 场景 | 推荐类名 | 示例页面 |
|------|----------|----------|
| UUID、任务 ID、Celery ID | `font-mono text-xs` | 任务详情 |
| API Key、JSON、提示词正文、合规规则 | `font-mono text-xs` ~ `text-sm` | 模型目录、工具配置、提示词编辑 |
| 对话中的代码块 | `font-mono text-[11px]` + `pre` | 智能体对话 |
| 快捷键提示 | `font-mono text-[10px]` | 流程画布 |

**约定**

- 等宽仅用于**可复制的技术内容**；普通说明文案仍用 `font-sans`（默认）。
- 字号比同级正文略小一级（多为 `text-xs`），避免与界面主字体抢视觉重心。
- 两端（`workbench` / `admin`）写法保持一致；运营后台模型表单的 `model_code`、`model_name` 等同理。

---

## 4. 布局结构

### 4.1 租户工作台（`workbench`）

```
┌─────────────────────────────────────────────────────────┐
│ 顶栏 h-14：BrandHeader · WorkbenchHeaderNav · UserMenu   │
├─────────────────────────────────────────────────────────┤
│ 主内容区 bg-surface-muted（p-4 lg:px-6）                 │
│   · 资源列表页：resource-page-shell (max-w-screen-2xl)   │
│   · 卡片网格：1→2→3→4 列；`resource-page-shell` 内 2xl 为 5 列 │
│   · 全屏页（对话/画布）：full-bleed，无 max-width        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 组织设置（`/system/*`，原「系统管理」）

```
┌──────────┬──────────────────────────────────────────────┐
│ 侧栏 w-60 │ 主内容                                        │
│ BrandHeader│                                              │
│ SYSTEM_NAV │                                              │
└──────────┴──────────────────────────────────────────────┘
```

产品文案逐步由「系统管理」改为 **「组织设置」**；路由仍为 `/system/*`。

### 4.4 运营后台（`admin`）

- 侧栏 `w-60`，顶栏 `h-12`，配色 token 与租户端一致。
- 管理类组件前缀：`admin-nav-item` / `admin-nav-item-active`（定义于 `ui/admin/app/globals.css`）。

### 4.5 登录页

- 左侧 Hero（`lg` 以上）：`CompanyLogo` `full` + MilesAi 产品文案 + 渐变 `from-brand-light`。
- 右侧表单：`card` 容器，`max-w-md` 居中。
- 移动端：仅右侧，顶部 `CompanyLogo` `md` + 产品标题。

---

## 5. 组件规范

### 5.1 Logo 组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `CompanyLogo` | `components/brand/company-logo.tsx` | `full` / `compact` / `mark`；`sm` / `md` / `lg` |
| `BrandHeader` | `components/brand/brand-header.tsx` | `compact` 行千里 + `productLine` |

```tsx
// 侧栏 / 顶栏（推荐）
<BrandHeader productLine="MilesAi · 工作台" href="/workbench/dashboard" />

// 登录 Hero
<CompanyLogo variant="full" size="lg" />

// 移动端登录顶栏
<CompanyLogo variant="full" size="md" showTagline={false} />
```

静态资源：`public/brand/logo-full.svg`、`logo-mark.svg`。

### 5.2 容器

| 类名 | 说明 |
|------|------|
| `.card` | 白底圆角卡片 + `border-line` + `shadow-card` |
| `.card-header` | 卡片顶栏分割 |
| `.card-body` | 内边距 `p-4` |

### 5.3 表单

| 类名 | 说明 |
|------|------|
| `.input-field` | 默认边框；`focus:border-brand` + `ring-brand/15` |

### 5.4 按钮

| 类名 | 场景 |
|------|------|
| `.btn-primary` | 主操作（橙底白字） |
| `.btn-ghost` | 次要 / 取消 |
| `.btn-sm-primary` | 表格内、紧凑主按钮 |
| `.btn-sm-outline` | 线框次要 |
| `.btn-sm-ghost` | 文字按钮 |

交互：`hover:bg-brand-dark`（主按钮）、`disabled:opacity-50`。

### 5.5 导航

| 类名 | 场景 |
|------|------|
| `.nav-item` / `.nav-item-active` | 系统侧栏 |
| `.header-nav-item` / `.header-nav-item-active` | 工作台顶栏 Tab |
| `.workbench-rail-item-*` | 智能体工作台左侧轨 |

选中态统一：`bg-brand-light` + `text-brand` + `font-medium`。

### 5.6 资源卡片列表（工作台 CRUD 页）

| 类名 | 说明 |
|------|------|
| `.resource-page-shell` | 列表页最大宽度容器（`max-w-screen-2xl`） |
| `.resource-card-grid` | 响应式网格 1→2→3→4 列；`resource-page-shell` 内 `2xl` 为 5 列 |
| `.resource-card` | 实体卡片；hover `border-brand/25` |
| `.resource-add-card` | 虚线「新建」卡片 |

### 5.7 弹窗与面板（Dialog / Sheet）

工作台 CRUD 的创建、编辑、确认统一走 `components/resource/ResourceDialog.tsx`；语义化包装见 `ConfirmDialog`、`PromptDialog`。

**权威实现**：`ResourceDialog` · 规范本文 §5.7 · `AppShell` 顶栏高度 `h-14`（`top-14` 与 sheet 对齐）。

#### 5.7.1 设计原则

| 原则 | 说明 |
|------|------|
| **分级而非一刀切** | 按任务复杂度选档位；简单打断用居中弹窗，复杂配置用 sheet |
| **保留全局上下文** | 默认保留 App Header（品牌、模块 Tab、用户菜单）；避免无故 `fullscreen` 盖住顶栏 |
| **单一滚动容器** | 内容区内部滚动，标题栏 / 底栏固定；禁止整页与弹窗双滚动 |
| **可预期退出** | 关闭按钮、Esc、（`md`/`lg`）点击遮罩；有未保存改动时二次确认 |
| **footer 右对齐** | 取消 `btn-ghost` + 主操作 `btn-primary`；destructive 用 ConfirmDialog |

#### 5.7.2 尺寸档位（`size`）

```
┌─────────────────────────────────────────────────────────────┐
│ App Header  h-14  （sheet 保留；fullscreen 会盖住 — 不推荐）   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   sheet：fixed top-14 inset-x-0 bottom-0                    │
│   · 主内容区全高 · max-w-5xl 居中 · 无遮罩                    │
│                                                             │
│   md / lg：居中浮层 + bg-ink/30 遮罩 · max-h-[90vh]          │
│   · md max-w-lg  · lg max-w-3xl                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| `size` | 布局 | 最大宽度 | 遮罩 | 典型场景 |
|--------|------|----------|------|----------|
| `md` | 居中浮层 | `max-w-lg` | ✅ `bg-ink/30` | 确认框、标签管理、2–4 字段短表单 |
| `lg` | 居中浮层 | `max-w-3xl` | ✅ | 试调用、文档分块预览、中等表单 |
| **`sheet`** | **顶栏下铺满** | 内容 `max-w-5xl` 居中 | ❌ | **多 Section / 多步 / 大段可编辑内容** |
| `fullscreen` | `inset-0` 全视口 | `max-w-5xl` | ❌ | **仅**无 App Shell 的独立页；新功能勿用 |

#### 5.7.3 选型表（工作台）

| 场景 | 推荐 `size` | 说明 |
|------|-------------|------|
| 删除 / 驳回 / 二次确认 | `md`（`ConfirmDialog`） | 强打断、秒级完成 |
| 标签管理、技能空白创建 | `md` | 字段少 |
| 工具试调用、KB 文档分块 | `lg` | 只读或单次操作 |
| **工具创建/编辑**（HTTP + 参数 + 脚本） | **`sheet`** | 多 Section、脚本编辑区 |
| **智能体表单**（多步 Stepper） | **`sheet`** | 步骤多、绑定项多 |
| **智能体详情**（只读） | **`sheet`** 或 `lg` | 信息块多时可 sheet |
| **MCP 服务**、**模型**、**KB** 等短表单 | **`lg`** 或 **`md`** | 字段少、无大段代码，居中即可 |
| 登录 / 无顶栏页 | `fullscreen` 或独立路由 | 例外 |

**反模式**

- 复杂表单用 `lg` 导致小窗内长距滚动
- 新页面默认 `fullscreen` 隐藏模块导航
- 在 `sheet` 内再嵌套 `md`/`lg` 弹窗超过一层（确认框除外）

#### 5.7.4 布局结构

**居中弹窗（`md` / `lg`）**

```
┌─ 遮罩 ─────────────────────────┐
│  ┌─ dialog ──────────────────┐  │
│  │ 标题 + 关闭               │  │
│  │ 可滚动内容 (space-y-3)    │  │
│  │ footer（可选，右对齐）     │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**面板（`sheet` / `fullscreen`）— `PanelChrome`**

```
┌─ header：标题 + 关闭 ─────────────────────┐
├─ 可滚动 body（px-6 py-6，max-w-5xl 居中）─┤
├─ footer（可选，border-t，按钮右对齐）──────┤
└──────────────────────────────────────────┘
```

- 多步表单：步骤条放在 **body 顶部**，不另加一层 header
- 表单分区：用 `rounded-xl border border-line` 的 `Section` 卡片（见 `ToolCreateDialog`）
- 长列表 / 代码：占满 body 剩余高度，`textarea` 用 `min-h-[200px]`

#### 5.7.5 交互行为

| 行为 | `md` / `lg` | `sheet` / `fullscreen` |
|------|-------------|-------------------------|
| Esc 关闭 | ✅ | ✅ |
| 点击遮罩关闭 | ✅ | —（无遮罩） |
| `body` 滚动锁定 | — | ✅ |
| 打开时焦点 | 对话框内 | 对话框内 |
| 关闭后 | 列表滚动位置 / 筛选保持不变 | 同左 |
| 未保存离开 | 业务层 `ConfirmDialog` | 同左 |

#### 5.7.6 包装组件

| 组件 | 路径 | 用途 |
|------|------|------|
| `ResourceDialog` | `components/resource/ResourceDialog.tsx` | 通用壳层 |
| `ConfirmDialog` | `components/resource/ConfirmDialog.tsx` | 确认 / 删除（`destructive`） |
| `PromptDialog` | `components/resource/PromptDialog.tsx` | 单行/短文本输入 |

```tsx
// 复杂创建/编辑（推荐）
<ResourceDialog open={open} title="新增工具" size="sheet" onClose={onClose} footer={footer}>
  {formContent}
</ResourceDialog>

// 轻量确认
<ConfirmDialog open={open} title="删除工具" destructive onConfirm={onDelete} onClose={onClose} />
```

#### 5.7.7 迁移约定

1. 新增复杂表单 **默认 `sheet`**，不再新增 `fullscreen`
2. **`sheet`**：`AgentFormDialog`、`A2aHostFormDialog`、`ToolCreateDialog` 等（多步 / 多 Section / 脚本）
3. **`lg` / `md`**：MCP、模型、KB 等字段有限的短表单，保持居中弹窗
4. 修改 `ResourceDialog` 时同步更新本节与组件 JSDoc

---

## 6. 图标与插图

- 导航图标：`SystemNavIcon` / `AdminNavIcon`（内联 SVG，随 `text-brand` / `text-ink-muted` 变色）。
- 登录 Hero 装饰：几何图形 + `text-brand/10`，不使用第三方插图库。
- 用户头像占位：圆形 `bg-brand` + 首字母（`UserMenu`）。

---

## 7. 动效与交互

- 过渡：组件类统一 `transition`（颜色、边框、阴影）。
- 导航/卡片 hover：浅色背景或边框提亮，避免 scale 动画干扰密集后台操作。
- 加载：对话区 `animate-pulse` 圆点（`text-brand`）。
- 焦点：表单 `ring-2 ring-brand/15`，保证键盘可访问性。
- **弹窗**：档位与行为见 [§5.7 弹窗与面板](#57-弹窗与面板dialog--sheet)。

---

## 8. 两端差异

| 项目 | `workbench` | `admin` |
|------|------------|------------------|
| 色彩 token | 相同 | 相同 |
| Logo 组件 | `components/brand/*` | 副本同步维护 |
| 导航类名 | `nav-item-*` | `admin-nav-item-*` |
| 顶栏高度 | `h-14` | `h-12` |
| 产品线文案 | `MilesAi · 工作台` / `MilesAi · 组织设置` | `MilesAi · 管理后台` |

修改品牌色时，**须同时更新** 两端 `tailwind.config.ts` 与 `globals.css`。

---

## 9. 开发约定

1. **优先使用 token**：`text-brand`、`bg-brand-light`、`border-line`，避免魔法色 `#E66432` 散落（Logo 组件常量除外）。
2. **新页面**：列表型 CRUD 复用 `resource-*` 类；表单页用 `card` + `input-field` + `btn-primary`。
3. **新强调色**：先在本规范 §2 登记，再写入 Tailwind。
4. **Logo**：导航只用 `BrandHeader`；不要并排 `mark` + `compact` 重复「行千里」。
5. **弹窗**：按 §5.7 选型；复杂表单用 `size="sheet"`，禁止新功能使用 `fullscreen` 盖住 App Header。
6. **Lint**：组件目录 `components/brand/`、`components/layout/` 为布局与品牌权威实现。
7. **必要链路注释**：新增或改动跨文件流程时，在 `ui/workbench/lib/chains.ts` 登记章节，并在入口文件（`lib/*`、`hooks/*`、页面顶部）注明章节号；列表页可参考 `app/workbench/flows/page.tsx`。已覆盖：全部 `app/**` 页面、`lib` 业务模块、`hooks`、各域主要 `components`；纯品牌/图表/`components/ui` 可不注释。

### 9.1 必要链路索引

权威清单：`ui/workbench/lib/chains.ts`（鉴权、API、列表页、枚举 meta、对话、流程、导航、知识库、技能包、Cron 等）。枚举字典另见 `lib/enum-meta.ts` 与 [hooks.md](../guides/hooks.md) §9。

| 章节 | 场景 | 关键文件 |
|------|------|----------|
| §1 | 登录与受保护路由 | `auth-store.ts`、`app/login`、`AppShell` |
| §2 | HTTP 与错误文案 | `api.ts`、`api-error.ts` |
| §3 | 工作台 CRUD 列表 | `use-paged-list.ts`、`ResourceListLayout`、`use-confirm-action.tsx` |
| §4 | 枚举展示 | `enum-meta.ts`、`use-*-meta.ts`、`*-labels.ts` |
| §5 | 智能体对话 | `chat-sessions.ts`、`agents/chat`、`agent-steps.ts` |
| §6 | 流程编排 | `flow-nodes.ts`、`flows/[id]/edit`；见 [flows.md](../guides/flows.md) |
| §7 | 导航壳层 | `nav-config.ts`、`AppShell`、`SystemShell` |
| §8 | KB 文档入库 | `document-status.ts`、`kb/[id]` |
| §9 | 技能包编辑器 | `skills/[id]`、`skill-md.ts`；references/scripts 分组、layout 索引、`reindexSkillPackage` |
| §11 | MCP | `mcp/page`、`mcp-labels.ts` |
| §12 | 应用市场 | `marketplace/page`、`marketplace-labels.ts` |
| §13 | 合规 | `compliance/page`、`compliance-labels.ts` |
| §14 | 监控 | `monitor/page`、`monitor-labels.ts` |
| §15 | 概览 / 重定向 | `dashboard/page`、`app/page.tsx` |

---

## 10. 参考文件速查

```
ui/workbench/
├── lib/chains.ts            # 必要链路索引（§9.1）
├── lib/enum-meta.ts         # 枚举 meta 契约（§4）
├── lib/api.ts               # API 客户端（§2）
├── lib/auth-store.ts        # 鉴权（§1）
├── lib/fonts.ts             # next/font Noto Sans SC（appFont）
├── lib/font-family.ts       # Tailwind font-sans 栈（供 tailwind.config 引用）
├── app/globals.css          # CSS 变量 + body 字体与抗锯齿
├── tailwind.config.ts       # 设计 token（含 fontFamily.sans）
├── components/brand/        # CompanyLogo, BrandHeader
├── public/brand/            # logo-full.svg, logo-mark.svg
├── components/layout/       # AppShell, SystemSidebar, LoginHero
└── components/resource/   # ResourceDialog, ConfirmDialog（§5.7）

ui/admin/              # 同上：lib/fonts.ts、font-family.ts、globals、tailwind 与租户端保持一致
```

相关文档：[technical-design.md](../architecture/technical-design.md)（系统架构）、根目录 [README.md](../README.md)（启动与端口）。
