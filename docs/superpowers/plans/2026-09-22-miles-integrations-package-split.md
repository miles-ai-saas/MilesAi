# miles-integrations 第 11 包拆分 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将纯 L3 的 `miles_ai.integrations` 整树拆为独立 workspace 包 `miles-integrations`（import 根 `miles_integrations`），硬切换、不留兼容层，并用包级 layers 冻结 `miles_ai → miles_integrations → miles_core`。

**Architecture:** 前置内部分层归位已清零 `integrations → rag/flow_runtime`。本计划做物理迁移动 + 全仓 import 改写 + 依赖归属 + 契约升级；不改业务逻辑。

**Tech Stack:** uv workspace、hatchling、import-linter、ruff（含 isort `I`）、pytest。

**Spec:** [docs/superpowers/specs/2026-09-22-miles-integrations-package-split-design.md](../specs/2026-09-22-miles-integrations-package-split-design.md)

## Global Constraints

- 所有后端命令在 `/Users/xiezhigang/Projects/miles/MilesAI/backend` 下执行；`make check` 在**仓库根**。
- 测试一律 `.venv/bin/python -m pytest`（`tests.paths` 依赖 `backend/` 在 `sys.path`）。
- 基线（支线起点，实施前以 Task 0 实测为准；写计划时 HEAD=`119f1ac4`）：**1517 tests collected**；`lint-imports` = **8 kept, 0 broken**；`integrations → rag/flow_runtime` 反向边 = **0**。
- **纯搬迁：禁止改逻辑、断言、fixture、函数签名。** 唯一代码改写是 import / 模块路径字符串（含 monkeypatch）与 docstring 中的旧路径提及；以及本计划明确给出的新文件（包骨架 `__init__.py`、pyproject、契约、文档）。
- **硬切换：禁止保留 `miles_ai.integrations` 兼容壳或 re-export。**
- `git mv` 保留 rename 历史；每个 Task **一个**提交，message 用简体中文 Conventional Commits。
- **import 顺序**：ruff 已启用 `I`（isort）。改完 import 后跑 `.venv/bin/ruff check --select I --fix .`，再 `.venv/bin/ruff format .`；与 `--fix` 冲突时以 `--fix` 为准。
- 每个 Task 结束必须全绿：`ruff check .`、`ruff format --check .`、`lint-imports`、`pytest -q`、`export_openapi --check`（Task 0 除外）。
- 单文件 ≤ 500 行；新增模块须有中文 docstring。
- workspace 已是 `members = ["packages/*"]`，新包放入 `packages/miles-integrations/` 即自动入组。
- `.superpowers/` 已 gitignore，不要提交 brief/report。

### 实施前必读的现状事实（已实测，勿再重复调研）

- 锚定口径下 `^\s*(from|import)\s+miles_ai\.integrations` 约 **278** 条（packages + tests）；包内自引用约 **118** 处文本提及。
- monkeypatch / 字符串路径含 `miles_ai.integrations.` 的测试文件至少 **8** 个文件、**100+** 处——批量替换必须覆盖字符串，不只改 `from/import` 行。
- `langchain-openai` 在 `miles-ai` 的 pyproject 中声明，但源码**零引用**——迁出后从 `miles-ai` **删除**，**不必**加入 `miles-integrations`（除非迁移后实测需要）。
- `Pillow`：`rag/parse/image_parser.py` 与 `embeddings/providers/clip.py` 都用 → **两边都声明**。
- `httpx`：仅 integrations 内使用（portal 已自有）→ 归 `miles-integrations`；`miles-ai` 可删（若迁后无残留）。
- `tests/test_tests_layout.py` 要求 `tests/miles_integrations/<子路径>/` 对应 `packages/miles-integrations/src/miles_integrations/<子路径>/`——测试目录必须 `git mv`，不能只改 import。

---

### Task 0: 记录实施基线

**Files:** 无改动（只产出 `/tmp` 快照）

- [ ] **Step 1: 记录 HEAD 与契约数**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git rev-parse HEAD | tee /tmp/mi-split-base.txt
cd backend
.venv/bin/lint-imports | tee /tmp/mi-split-lint-before.txt | tail -15
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/mi-names-before.txt
wc -l /tmp/mi-names-before.txt
rg -n --no-heading '^\s*(from|import)\s+miles_ai\.(rag|flow_runtime)' -g '**/integrations/**' packages; echo "--- 期望：无输出（反向边仍为 0）"
```

Expected: `lint-imports` 末行 `Contracts: 8 kept, 0 broken.`；用例名文件约 1517 行；反向边无输出。

- [ ] **Step 2: 控制器记录支线起点 SHA**

把 Step 1 的 HEAD 写入进度 ledger，作为终审 BASE。本 Task **不提交**。

---

### Task 1: 建包、整树迁入、全仓硬改 import、调整依赖

**Files:**
- Create: `packages/miles-integrations/pyproject.toml`
- Create: `packages/miles-integrations/src/miles_integrations/__init__.py`（随后被 git mv 覆盖目录——见步骤说明）
- Move: `packages/miles-ai/src/miles_ai/integrations/**` → `packages/miles-integrations/src/miles_integrations/**`
- Move: `tests/miles_ai/integrations/**` → `tests/miles_integrations/**`
- Modify: `packages/miles-ai/pyproject.toml`
- Modify: `packages/miles-portal/pyproject.toml`
- Modify: `packages/miles-server/pyproject.toml`
- Modify: `packages/miles-worker/pyproject.toml`
- Modify: `tests/paths.py`（增加 `MILES_INTEGRATIONS`）
- Modify: 全仓凡含 `miles_ai.integrations` 的 `.py` / 文档内代码路径字符串（批量替换）

**Interfaces:**
- Produces: 可 import 的 `miles_integrations.*`；`miles_ai` 仅含 `rag/` + `flow_runtime/`

- [ ] **Step 1: 创建包目录与 `pyproject.toml`**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p packages/miles-integrations/src/miles_integrations
```

写入 `packages/miles-integrations/pyproject.toml`（全文）：

```toml
[project]
name = "miles-integrations"
version = "0.1.0"
description = "AI 第三方适配层（LangChain / LangGraph / LiteLLM / DeepAgents / embeddings / generative / rerank）"
requires-python = ">=3.11"
dependencies = [
    "miles-core",
    "miles-common",
    "langchain-core>=0.3.0",
    "langgraph>=1.2.0",
    "langgraph-checkpoint-redis>=0.4.0",
    "litellm>=1.85.1",
    "sentence-transformers>=3.3.0",
    "deepagents>=0.5.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "Pillow>=10.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/miles_integrations"]

[tool.uv.sources]
miles-core = { workspace = true }
miles-common = { workspace = true }
```

临时占位（下一步 git mv 会用真实树替换；若 mkdir 时已有空 `__init__.py`，git mv 前删掉以免冲突）：

```bash
# 占位仅防 hatch 抱怨；紧接着会被源码树替换
printf '%s\n' '"""AI 第三方适配层（L3）。"""' > packages/miles-integrations/src/miles_integrations/__init__.py
```

- [ ] **Step 2: `git mv` 源码整树**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
# 去掉占位，让出目录给 git mv
rm -f backend/packages/miles-integrations/src/miles_integrations/__init__.py
# 把 integrations 目录下所有内容迁到新包（含 __init__.py）
git mv backend/packages/miles-ai/src/miles_ai/integrations/__init__.py \
       backend/packages/miles-integrations/src/miles_integrations/__init__.py
for name in chat deepagents embeddings generative http_constants.py langchain langgraph litellm rerank; do
  git mv "backend/packages/miles-ai/src/miles_ai/integrations/$name" \
         "backend/packages/miles-integrations/src/miles_integrations/$name"
done
rmdir backend/packages/miles-ai/src/miles_ai/integrations 2>/dev/null || \
  rm -rf backend/packages/miles-ai/src/miles_ai/integrations
ls backend/packages/miles-ai/src/miles_ai/
ls backend/packages/miles-integrations/src/miles_integrations/
```

Expected: `miles_ai` 下列出 `flow_runtime`、`rag`、`__init__.py`（无 `integrations`）；新包列出原 integrations 子树。

- [ ] **Step 3: `git mv` 测试镜像目录**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_integrations
git mv tests/miles_ai/integrations/deepagents tests/miles_integrations/deepagents
git mv tests/miles_ai/integrations/embeddings tests/miles_integrations/embeddings
git mv tests/miles_ai/integrations/generative tests/miles_integrations/generative
git mv tests/miles_ai/integrations/langchain tests/miles_integrations/langchain
git mv tests/miles_ai/integrations/litellm tests/miles_integrations/litellm
git mv tests/miles_ai/integrations/rerank tests/miles_integrations/rerank
rmdir tests/miles_ai/integrations 2>/dev/null || rm -rf tests/miles_ai/integrations
ls tests/miles_ai/
ls tests/miles_integrations/
```

Expected: `tests/miles_ai/` 无 `integrations/`；`tests/miles_integrations/` 有 6 个子目录。

- [ ] **Step 4: 全仓批量替换路径字符串**

**必须**用字面量全局替换（覆盖 import 与 monkeypatch 字符串），在 `backend/` 下：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
# 仅改 .py；docs 留 Task 3
rg -l 'miles_ai\.integrations' packages tests | while read -r f; do
  perl -pi -e 's/miles_ai\.integrations/miles_integrations/g' "$f"
done
rg -n 'miles_ai\.integrations' packages tests; echo "--- 期望：无输出"
```

Expected: 无输出。

- [ ] **Step 5: 更新 `tests/paths.py`**

在 `MILES_AI = ...` 一行后追加：

```python
MILES_INTEGRATIONS = PACKAGES / "miles-integrations" / "src" / "miles_integrations"
```

- [ ] **Step 6: 改写 `miles-ai/pyproject.toml`**

`dependencies` 改为（去掉已迁出的 litellm / deepagents / sentence-transformers / langgraph-checkpoint-redis / langchain-openai / httpx；保留 LC/LG 核心与 parse 依赖；**增加** `miles-integrations`）：

```toml
dependencies = [
    "miles-core",
    "miles-common",
    "miles-integrations",
    "langchain-core>=0.3.0",
    "langchain-community>=0.3.0",
    "langchain-text-splitters>=0.3.0",
    "langgraph>=1.2.0",
    "pydantic>=2.10.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "Pillow>=10.0.0",
    # packages/miles-ai/.../rag/parse/backends/pypdf.py 用 langchain_community.PyPDFLoader
    "pypdf>=5.1.0",
    "docling>=2.0.0",
    "pytesseract>=0.3.10",
    "openai-whisper>=20231117",
]
```

`[tool.uv.sources]` 增加：

```toml
miles-integrations = { workspace = true }
```

- [ ] **Step 7: 上层包显式依赖 `miles-integrations`**

对 `packages/miles-portal/pyproject.toml`、`packages/miles-server/pyproject.toml`、`packages/miles-worker/pyproject.toml` 各做两处改动：

1. `dependencies` 列表增加 `"miles-integrations",`（建议紧挨 `miles-ai`）
2. `[tool.uv.sources]` 增加 `miles-integrations = { workspace = true }`

- [ ] **Step 8: `uv sync` 并验证**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
uv sync
.venv/bin/python -c "import miles_integrations; import miles_integrations.langgraph.checkpointer; print('ok', miles_integrations.__file__)"
.venv/bin/ruff check --select I --fix .
.venv/bin/ruff format .
.venv/bin/ruff check . && .venv/bin/ruff format --check .
# 注意：此时 .importlinter 尚未认识新包，lint-imports 可能报 root 未声明——
# 本 Task 先跑 pytest / openapi；契约改在 Task 2。若 lint-imports 因缺 root 失败，可暂时跳过，但须在报告中写明。
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: pytest `1517 passed`；OpenAPI OK。若 `lint-imports` 因未登记 `miles_integrations` 失败，属预期，Task 2 修复。

> 若 pytest 在 Task 2 前因 import-linter 插件钩子失败（少见），先完成 Task 2 的 root_packages 登记再重跑——但优先把 root 登记放进 Task 2 开头，本步以 pytest 为准。

- [ ] **Step 9: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): 拆出 miles-integrations 并硬切换全仓 import

将纯 L3 的 integrations 整树迁入第 11 个 workspace 包，import 根改为
miles_integrations；litellm / deepagents / sentence-transformers 等仅 L3
依赖随包迁出。不留 miles_ai.integrations 兼容壳。
EOF
git log --oneline -1
```

---

### Task 2: 升级 import-linter 契约（红/绿）

**Files:**
- Modify: `backend/.importlinter`

**Interfaces:**
- Consumes: Task 1 产出的 `miles_integrations` 包
- Produces: 包级 layers 含 `miles_integrations`；包内 `ai-internal-layers` 收窄为两层；forbidden 同步

- [ ] **Step 1: 改写 `.importlinter`**

1. `root_packages` 在 `miles_ai` 之后插入 `miles_integrations`：

```ini
root_packages =
    miles_common
    miles_exec
    miles_core
    miles_ai
    miles_integrations
    miles_portal
    miles_admin
    miles_openapi
    miles_server
    miles_worker
    miles_runner
```

2. 包级 `layers` 在 `miles_ai` 与 `miles_core` 之间插入：

```ini
layers =
    miles_server | miles_worker | miles_runner
    miles_openapi | miles_admin
    miles_portal
    miles_ai
    miles_integrations
    miles_core
    miles_exec
    miles_common
```

3. `no-ai-to-portal` 的 `source_modules` 改为：

```ini
source_modules =
    miles_ai
    miles_integrations
```

4. `runner-minimal` 的 `forbidden_modules` 增加 `miles_integrations`（与 `miles_ai` 并列）。

5. `core-no-ai` 的 `forbidden_modules` 改为：

```ini
forbidden_modules =
    miles_ai
    miles_integrations
```

6. 收窄 `ai-internal-layers`（全文替换该契约段）：

```ini
# miles_ai 包内分层：编排（flow_runtime）在上、RAG（rag）在下。
# 原第三层 integrations 已拆为独立包 miles_integrations（2026-09-22），由包级 layers 约束。
# 本契约额外冻结 rag ✗→ flow_runtime（该边为 0，反向必成环）。
[importlinter:contract:ai-internal-layers]
name = miles_ai 内部分层（编排在上，RAG 在下）
type = layers
layers =
    miles_ai.flow_runtime
    miles_ai.rag
```

- [ ] **Step 2: 红测**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
printf '\nfrom miles_ai.rag.chunk import split_text  # noqa: F401\n' >> packages/miles-integrations/src/miles_integrations/langchain/chat_models.py
.venv/bin/lint-imports | tee /tmp/mi-split-red.txt | tail -20
git checkout -- packages/miles-integrations/src/miles_integrations/langchain/chat_models.py
git status --porcelain; echo "--- 期望：空"
```

Expected: 输出含 `包分层方向` 或明确指明 `miles_integrations` → `miles_ai` 违规；末行含 `broken`（例如 `N kept, 1 broken`）。**不得**仍显示「契约空转全绿」。撤销后工作区干净。

- [ ] **Step 3: 绿测**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/lint-imports | tee /tmp/mi-split-green.txt | tail -20
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: 全部 KEPT（契约总数 = 原 8 条结构仍在，仅内容升级；末行 `X kept, 0 broken`）；pytest 1517；OpenAPI OK。

- [ ] **Step 4: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add backend/.importlinter
git commit -F- <<'EOF'
ci(ai): 包级 layers 插入 miles_integrations 并收窄包内契约

integrations 拆包后由包级 layers 冻结 miles_ai → miles_integrations；
ai-internal-layers 收窄为 flow_runtime → rag。forbidden 同步禁止
integrations 依赖 portal，以及 core/runner 依赖 integrations。
EOF
git log --oneline -1
```

---

### Task 3: 同步文档与 spec「已实施」

**Files:**
- Modify: `docs/architecture/layering.md`（凡写 `miles_ai/integrations` 或 `miles_ai.integrations` 处）
- Modify: `docs/superpowers/specs/2026-09-22-miles-integrations-package-split-design.md`（§10 补已实施）
- Modify: `docs/superpowers/specs/2026-09-22-miles-ai-internal-layering-design.md`（§9 后续项标注已由本拆包完成——一行交叉引用即可）

**Interfaces:** 无代码接口

- [ ] **Step 1: 盘点并改 `layering.md`**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n 'miles_ai\.integrations|miles_ai/integrations|integrations/' docs/architecture/layering.md
```

按下列原则逐条改（以文本为准，行号可能漂移）：

| 主题 | 改为 |
|------|------|
| L3 路径 | `miles_integrations/`（包 `miles-integrations`） |
| 包表 `miles_ai` 行 | 仅 L2：`rag/` + `flow_runtime/` |
| 新增包表行 | `miles_integrations` \| L3 适配 \| L3 |
| 目录树 | `miles-ai` 下删除 `integrations/`；并列画出 `miles-integrations/` |
| 包内分层说明 | 改为 `flow_runtime → rag`；跨包由包级 layers 约束 `miles_ai → miles_integrations` |
| 强制机制契约计数 | 重新清点 `.importlinter` 契约条数后写入（实施时 `rg -c '^\[importlinter:contract:' backend/.importlinter`） |

- [ ] **Step 2: 清掉仓库内残留旧路径（除历史 plan/spec 叙述）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n 'miles_ai\.integrations' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/2026-09-22-miles-ai-internal-layering*' .
```

对命中的 `docs/` / `ui/` 等非历史叙述文件改为 `miles_integrations`。`docs/superpowers/specs/2026-09-22-miles-ai-internal-layering-design.md` 中描述「当时现状」的句子可保留，但在 §9/修订记录加一句：「第 11 包拆分见 2026-09-22-miles-integrations-package-split-design.md（已实施）。」

- [ ] **Step 3: 本 spec 补「已实施」**

在 `docs/superpowers/specs/2026-09-22-miles-integrations-package-split-design.md` 文首状态改为 **已实施**，并在 §10 追加：

```markdown
### 2026-09-22：已实施

Task 1–3 落地。与本文无偏差。验收：全仓无 `miles_ai.integrations` 生产 import；
`lint-imports` 全绿；pytest collect-only 与基线一致。
```

- [ ] **Step 4: 全绿门禁 + 用例快照**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make check
cd backend
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/mi-names-after.txt
diff /tmp/mi-names-before.txt /tmp/mi-names-after.txt && echo "用例集合零变化"
rg -n '^\s*(from|import)\s+miles_ai\.integrations' packages tests; echo "--- 期望：无输出"
```

Expected: `make check` 全绿；diff 无输出；旧 import 无输出。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
docs(ai): 同步 layering 与拆包已实施记录

第 11 包 miles-integrations 落地后，更新架构文档中的 L3 路径与契约说明，
并在拆包 design 标记已实施。
EOF
git log --oneline -1
```

---

## 收尾验收（对照 spec §7）

- [ ] `packages/miles-ai/src/miles_ai/` 无 `integrations/`
- [ ] 旧 import 路径 0
- [ ] `lint-imports` 全 KEPT
- [ ] collect-only 与 `/tmp/mi-names-before.txt` 一致
- [ ] OpenAPI 零漂移

---

## 执行交接

Plan complete。实施时推荐 **Subagent-Driven**：每 Task 派新 subagent，任务间两阶段评审。
