# MilesAi 运营后台（admin_frontend）

独立 Next.js 应用，对接平台运营 API `/api/admin/v1`，与租户 AI 工作台（`frontend`，端口 3000）分离部署。

## 本地开发

```bash
cd admin_frontend
cp .env.local.example .env.local
npm install
npm run dev
```

打开 http://localhost:3001 ，默认平台管理员：`platform` / `admin123`。

若浏览器报跨域，确认后端 `CORS_ORIGINS` 已包含运营后台地址（默认含 `3001`/`3002`），修改后需**重启 API**。

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `NEXT_PUBLIC_ADMIN_API_URL` | 运营 API 根路径 | `http://localhost:8000/api/admin/v1` |

## 页面路由

| 路径 | 功能 |
|------|------|
| `/login` | 平台管理员登录 |
| `/` | 运营概览 |
| `/tenants` | 租户列表与创建 |
| `/tenants/[id]` | 租户详情、配额、删除 |
| `/billing` | 套餐与账单 |
| `/risk` | 风险事件、IP 黑名单、限流 |
| `/audit` | 审计日志 |
| `/profile` | 改密、会话列表 |

## Docker

在 `docker/docker-compose.yml` 中已包含 `admin-web` 服务（端口 3001）。全栈启动：

```bash
cd docker
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build
```

运营后台：http://localhost:3001
