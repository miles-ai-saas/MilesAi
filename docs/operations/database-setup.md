# 数据库创建与初始化

> 类型：运维指南 | 状态：已实现 | 关联：[README.md](../README.md)、[../../docker/README.md](../../docker/README.md)

MilesAi 业务数据存储在 **PostgreSQL 15+**，表结构由 **Alembic** 管理。向量数据在 Weaviate，文件在 MinIO，不在 PostgreSQL 中建库说明范围内。

---

## 一、前置条件

1. 已安装 PostgreSQL 15 或以上（本地或 Docker）。
2. 已在 `backend/.env`（或项目根 `.env`）中配置：

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=milesai
```

3. 后端依赖已安装：`pip install -e ".[dev]"`（在 `backend` 目录下）。

---

## 二、创建数据库（三种方式）

### 方式 A：Docker 中间件（推荐，自动建库）

仅启动中间件栈时，PostgreSQL 会根据环境变量 **自动创建** 数据库和用户，无需手动 `CREATE DATABASE`。

```bash
cp .env.example .env
cd docker
docker compose -f docker-compose.infra.yml up -d
```

`docker-compose.infra.yml` 中等价配置：

```yaml
POSTGRES_USER: postgres
POSTGRES_PASSWORD: postgres
POSTGRES_DB: milesai
```

此时 `POSTGRES_HOST` 在 **容器内** 为 `postgres`，在 **宿主机连接** 时为 `localhost`（端口映射 `5432`）。

---

### 方式 B：本机已安装 PostgreSQL（手动建库）

使用超级用户（如 `postgres`）登录后执行：

```bash
psql -U postgres
```

```sql
-- 使用默认超级用户 postgres / postgres 时，仅需创建业务库
CREATE DATABASE milesai
  ENCODING 'UTF8'
  LC_COLLATE 'en_US.UTF-8'
  LC_CTYPE 'en_US.UTF-8'
  TEMPLATE template0;
```

macOS 若 locale 不同，可简化为：

```sql
CREATE DATABASE milesai ENCODING 'UTF8';
```

验证连接：

```bash
psql -h localhost -U postgres -d milesai -c "SELECT 1;"
```

---

### 方式 C：仅启动中间件容器，后端仍在本机跑

```bash
cd docker
docker compose -f docker-compose.infra.yml up -d
```

`backend/.env` 使用：

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

数据库仍由容器启动时自动创建，与方式 A 相同。

---

## 三、初始化表结构（迁移）

在 **`backend` 目录** 下执行 Alembic，将创建全部业务表：

| 版本 | 文件 | 内容 |
|------|------|------|
| 001 | `001_initial_schema.py` | **唯一迁移**：按当前 ORM `metadata.create_all` 创建全部业务表（含知识库、智能体、附件、检索日志等） |

```bash
cd backend
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 务必在 backend 目录执行
alembic upgrade head
# 等价：python -m alembic -c alembic.ini upgrade head
```

成功时可看到当前版本为 `001`。

查看当前版本：

```bash
alembic current
```

查看迁移历史：

```bash
alembic history --verbose
```

> **说明：** 启动 API 时（`uvicorn app.main:app`）也会在 lifespan 中自动执行 `alembic upgrade head`。手动执行一遍更便于排错；生产环境建议部署流程中 **显式跑迁移**，不 sole 依赖启动时迁移。

**从旧多文件迁移（002–021）升级到此版本：**

- 若表结构已与当前代码一致：`cd backend && alembic stamp 001`
- 若需干净库：删库重建后 `alembic upgrade head`，再 `python cli.py init-db --seed-only`

---


## 四、种子数据（默认管理员）

迁移完成后，在 **`backend` 目录** 手动执行初始化脚本（与业务代码解耦，API 启动**不会**自动写种子）：

```bash
cd backend
python cli.py init-db              # 迁移 + 全量种子（若已迁移过可 --seed-only）
python cli.py init-db --seed-only
python cli.py seed all             # 仅种子，等价于 init-db --seed-only
```

| 配置项 | 默认值 |
|--------|--------|
| `SEED_ADMIN_USERNAME` | admin |
| `SEED_ADMIN_PASSWORD` | admin123 |
| `SEED_ADMIN_EMAIL` | admin@local.dev |
| `SEED_TENANT_NAME` | 默认租户 |

种子实现位于 `backend/scripts/seed/`（租户、合规、应用市场、运营账号、内置模型目录等）。可按域单独执行：`python cli.py seed tenant` 等。

### 工作台分类（`sys_categories`）

默认定义见 [`backend/scripts/seed/data/sys_categories_defaults.json`](../../backend/scripts/seed/data/sys_categories_defaults.json)：

| domain | 默认分类（slug） |
|--------|------------------|
| `agent` | 未分类、客服、通用、合规、内部 |
| `prompt` | 未分类、通用、营销、研发 |
| `skill` | 未分类、通用、本地导入、Git导入、ZIP导入 |

写入命令（幂等，已存在 slug 不重复插入）：

```bash
cd backend
python cli.py seed categories   # 为所有租户补齐三域分类
python cli.py seed tenant       # 新建租户时也会调用 seed_categories_for_tenant
```

`seed all` / `init-db` 已包含 `seed_categories`。

```bash
uvicorn app.main:app --reload --port 8000
```

验证登录：

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

---

## 五、完整本地流程（ checklist ）

```bash
# 1. 环境变量
cd backend && cp .env.example .env

# 2. 启动中间件（二选一）
#    docker:  cd ../docker && docker compose -f docker-compose.infra.yml up -d
#    本机:    按「方式 B」建库

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 迁移 + 种子
python cli.py init-db

# 5. 启动 API
python cli.py serve
```

---

## 六、常用运维命令

### 回滚一个版本

```bash
alembic downgrade -1
```

### 回滚到初始前（清空所有表，慎用）

```bash
alembic downgrade base
```

### 重建库（开发环境）

```bash
# 删除并重建数据库
psql -U postgres -c "DROP DATABASE IF EXISTS milesai;"
psql -U postgres -c "CREATE DATABASE milesai ENCODING 'UTF8';"

cd backend && python cli.py init-db
```

### 连接串说明

应用内自动拼接（见 `app/core/config.py`）：

- 异步（FastAPI）：`postgresql+asyncpg://用户:密码@主机:端口/库名`
- 同步（Celery）：`postgresql://用户:密码@主机:端口/库名`

---

## 七、故障排查

| 现象 | 处理 |
|------|------|
| `connection refused` | 检查 Postgres 是否启动、`POSTGRES_HOST` / 端口 |
| `database "milesai" does not exist` | 按「方式 B」创建库，或检查 Docker `POSTGRES_DB` |
| `password authentication failed` | 核对 `.env` 与建库时密码是否一致 |
| `relation "users" does not exist` | 执行 `alembic upgrade head` |
| `No 'script_location' key found` | 先 `cd backend` 再执行，或 `python -m alembic -c alembic.ini upgrade head` |
| `password authentication failed` | 检查 `backend/.env` 是否为 `postgres` / `postgres` |
| `upgrade head` 无 `Running upgrade` 且没有表 | 运行 `python cli.py verify-db`；缺表则按「重建库」清 schema 后 `python cli.py init-db` |
| 迁移报 enum 已存在 | 多为重复执行，检查 `alembic current` 是否已是 `001` |

---

## 八、与 Weaviate / MinIO 的区别

| 存储 | 是否需要「建库」 | 初始化方式 |
|------|------------------|------------|
| PostgreSQL | **需要**（本文档） | `CREATE DATABASE` + `alembic upgrade head` |
| Weaviate | 无需建库名 | API/Worker 首次写入时自动 `ensure_schema` |
| MinIO | 无需建库名 | 首次上传时自动 `ensure_bucket` |

---

*文档随迁移版本更新；当前最新 revision：`003`。*
