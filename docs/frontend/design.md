# MilesAi 前端设计规范

> 适用范围：`frontend/`（租户 AI 工作台）、`admin_frontend/`（平台运营后台）  
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

常量定义：`frontend/components/brand/company-logo.tsx`（`COMPANY_ORANGE` / `COMPANY_TAGLINE`）。

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
| `frontend/tailwind.config.ts` | Tailwind 扩展色、阴影 |
| `frontend/app/globals.css` | CSS 变量 + 组件类 |
| `admin_frontend/tailwind.config.ts` | 与租户端保持一致 |
| `admin_frontend/app/globals.css` | 同上 |

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
- 两端（`frontend` / `admin_frontend`）写法保持一致；运营后台模型表单的 `model_code`、`model_name` 等同理。

---

## 4. 布局结构

### 4.1 租户工作台（`frontend`）

```
┌─────────────────────────────────────────────────────────┐
│ 顶栏 h-14：BrandHeader · WorkbenchHeaderNav · UserMenu   │
├─────────────────────────────────────────────────────────┤
│ 主内容区 bg-surface-muted                                │
│   · 资源列表页：resource-page-shell (max-w-7xl)          │
│   · 全屏页（对话/画布）：full-bleed，无 max-width        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 系统管理（`/system/*`）

```
┌──────────┬──────────────────────────────────────────────┐
│ 侧栏 w-60 │ 主内容                                        │
│ BrandHeader│                                              │
│ SYSTEM_NAV │                                              │
└──────────┴──────────────────────────────────────────────┘
```

### 4.3 运营后台（`admin_frontend`）

- 侧栏 `w-60`，顶栏 `h-12`，配色 token 与租户端一致。
- 管理类组件前缀：`admin-nav-item` / `admin-nav-item-active`（定义于 `admin_frontend/app/globals.css`）。

### 4.4 登录页

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
| `.resource-page-shell` | 列表页最大宽度容器 |
| `.resource-card-grid` | 响应式网格 1→4 列 |
| `.resource-card` | 实体卡片；hover `border-brand/25` |
| `.resource-add-card` | 虚线「新建」卡片 |

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

---

## 8. 两端差异

| 项目 | `frontend` | `admin_frontend` |
|------|------------|------------------|
| 色彩 token | 相同 | 相同 |
| Logo 组件 | `components/brand/*` | 副本同步维护 |
| 导航类名 | `nav-item-*` | `admin-nav-item-*` |
| 顶栏高度 | `h-14` | `h-12` |
| 产品线文案 | `MilesAi · 工作台` / `系统管理` | `MilesAi · 管理后台` |

修改品牌色时，**须同时更新** 两端 `tailwind.config.ts` 与 `globals.css`。

---

## 9. 开发约定

1. **优先使用 token**：`text-brand`、`bg-brand-light`、`border-line`，避免魔法色 `#E66432` 散落（Logo 组件常量除外）。
2. **新页面**：列表型 CRUD 复用 `resource-*` 类；表单页用 `card` + `input-field` + `btn-primary`。
3. **新强调色**：先在本规范 §2 登记，再写入 Tailwind。
4. **Logo**：导航只用 `BrandHeader`；不要并排 `mark` + `compact` 重复「行千里」。
5. **Lint**：组件目录 `components/brand/`、`components/layout/` 为布局与品牌权威实现。

---

## 10. 参考文件速查

```
frontend/
├── lib/fonts.ts             # next/font Noto Sans SC（appFont）
├── lib/font-family.ts       # Tailwind font-sans 栈（供 tailwind.config 引用）
├── app/globals.css          # CSS 变量 + body 字体与抗锯齿
├── tailwind.config.ts       # 设计 token（含 fontFamily.sans）
├── components/brand/        # CompanyLogo, BrandHeader
├── public/brand/            # logo-full.svg, logo-mark.svg
└── components/layout/       # AppShell, SystemSidebar, LoginHero

admin_frontend/              # 同上：lib/fonts.ts、font-family.ts、globals、tailwind 与租户端保持一致
```

相关文档：[technical-design.md](../architecture/technical-design.md)（系统架构）、根目录 [README.md](../README.md)（启动与端口）。
