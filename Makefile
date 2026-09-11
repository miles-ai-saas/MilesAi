# MilesAi —— 开发与运维快捷入口
#
# 本 Makefile 只封装仓库既有命令（见 README.md、backend/README.md），不引入额外构建系统。
# 运行 `make help` 查看全部可用命令。
#
# 可覆盖变量（示例：`make push-api TAG=v1.2.0`）：
#   REGISTRY  镜像仓库前缀
#   TAG       镜像 tag（默认 latest）
#   PLATFORM  构建目标平台（默认 linux/amd64；Apple Silicon 跨架构部署必须指定）
#   SEED      init-db 的种子范围（默认 all；可填 tenant/tools/mcp/…）
#   PY        后端解释器（默认自动探测 backend/.venv，否则 python3）
#   COMPOSE   Compose 命令（默认 `docker compose`，旧版可覆盖为 docker-compose）

MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
ROOT := $(patsubst %/,%,$(MAKEFILE_DIR))

BACKEND := $(ROOT)/backend
VENV := $(BACKEND)/.venv

# 用绝对路径，保证 `cd backend` 后仍可执行；优先虚拟环境，其次 PATH 中的 python3
PY ?= $(shell if [ -x "$(VENV)/bin/python" ]; then echo "$(VENV)/bin/python"; else echo python3; fi)
RUFF ?= $(shell if [ -x "$(VENV)/bin/ruff" ]; then echo "$(VENV)/bin/ruff"; else echo ruff; fi)

COMPOSE ?= docker compose
# 中间件与业务应用分属两套 Compose 文件（见 README「快速启动」）
COMPOSE_INFRA := $(COMPOSE) -f $(ROOT)/docker-compose.infra.yml
COMPOSE_APP := $(COMPOSE) -f $(ROOT)/docker-compose.yml

REGISTRY ?= registry.cn-shenzhen.aliyuncs.com/kye_secure
TAG ?= latest
PLATFORM ?= linux/amd64
SEED ?= all

# 复用同一套 buildx 参数；$(3) 传 --load 或 --push
define buildx_cmd
docker buildx build --platform $(PLATFORM) --progress=plain -t $(REGISTRY)/$(1):$(TAG) -f $(2) . $(3)
endef

.DEFAULT_GOAL := help

.PHONY: help env install install-backend install-ui \
	infra-up infra-down infra-ps infra-logs \
	up up-dev down ps logs restart \
	init-db migrate seed verify-db \
	serve worker beat \
	lint lint-backend lint-ui format format-check format-check-backend format-check-ui \
	test test-backend test-ui openapi-check openapi-write check check-ui \
	ui-dev ui-dev-admin ui-build ui-install \
	build-api build-worker build-mcp-runner build-all \
	push-api push-worker push-mcp-runner push-all \
	clean

##@ 帮助

help: ## 显示全部可用命令
	@awk 'BEGIN {FS = ":.*## "}; /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)}; /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

##@ 环境准备

env: ## 复制 .env.example → .env（仅在 .env 缺失时）
	@if [ -f "$(ROOT)/.env" ]; then echo ".env 已存在，跳过"; else cp "$(ROOT)/.env.example" "$(ROOT)/.env" && echo "已生成 .env，请按需修改基础设施地址"; fi

install-backend: ## 安装后端依赖（editable + dev extras）
	cd $(BACKEND) && $(PY) -m pip install -e ".[dev]"

install-ui: ## 安装前端依赖（shared → workbench → admin，npm ci）
	cd $(ROOT)/ui/shared && npm ci
	cd $(ROOT)/ui/workbench && npm ci
	cd $(ROOT)/ui/admin && npm ci

install: install-backend install-ui ## 安装后端与前端全部依赖

##@ 基础设施（docker-compose.infra.yml）

infra-up: ## 启动中间件（PG/Redis/MinIO/Milvus/Flower）
	$(COMPOSE_INFRA) up -d

infra-down: ## 停止中间件
	$(COMPOSE_INFRA) down

infra-ps: ## 查看中间件状态
	$(COMPOSE_INFRA) ps

infra-logs: ## 跟踪中间件日志
	$(COMPOSE_INFRA) logs -f

##@ 应用栈（docker-compose.yml）

up: ## 构建并启动应用栈（api/worker/beat/mcp-runner）
	$(COMPOSE_APP) up -d --build

up-dev: ## 启动应用栈并挂载 ./backend 实现热重载（--profile dev）
	$(COMPOSE_APP) --profile dev up -d --build

down: ## 停止应用栈
	$(COMPOSE_APP) down

ps: ## 查看应用栈状态
	$(COMPOSE_APP) ps

logs: ## 跟踪应用栈日志
	$(COMPOSE_APP) logs -f

restart: down up ## 重启应用栈

##@ 数据库（需数据库可达）

init-db: ## 迁移 + 全量种子（SEED 可覆盖范围）
	cd $(BACKEND) && $(PY) cli.py init-db

migrate: ## 仅执行 Alembic 迁移（alembic upgrade head）
	cd $(BACKEND) && $(PY) cli.py migrate

seed: ## 写入指定范围种子（默认 all）
	cd $(BACKEND) && $(PY) cli.py seed $(SEED)

verify-db: ## 校验核心表是否就绪
	cd $(BACKEND) && $(PY) cli.py verify-db

##@ 本地运行（后端）

serve: ## 启动 API（debug 时默认热重载）
	cd $(BACKEND) && $(PY) cli.py serve

worker: ## 启动 Celery Worker
	cd $(BACKEND) && $(PY) cli.py worker

beat: ## 启动 Celery Beat（智能体定时任务）
	cd $(BACKEND) && $(PY) cli.py beat

##@ 代码质量

lint-backend: ## 后端 ruff check
	cd $(BACKEND) && $(RUFF) check .

lint-ui: ## 前端 ESLint（workbench + admin）
	cd $(ROOT)/ui && npm run lint

lint: lint-backend lint-ui ## 后端 + 前端静态检查

format: ## 自动格式化（ruff format + prettier）
	cd $(BACKEND) && $(RUFF) format .
	cd $(ROOT)/ui && npm run format

format-check-backend: ## 校验后端格式（ruff format --check）
	cd $(BACKEND) && $(RUFF) format --check .

format-check-ui: ## 校验前端格式（prettier --check）
	cd $(ROOT)/ui && npm run format:check

format-check: format-check-backend format-check-ui ## 校验后端 + 前端格式

test-backend: ## 运行后端 pytest
	cd $(BACKEND) && $(PY) -m pytest -q

test-ui: ## 运行工作台前端单测（vitest）
	cd $(ROOT)/ui/workbench && npm run test

test: test-backend ## 运行后端测试（前端单测用 test-ui）

openapi-check: ## 校验 OpenAPI 快照无漂移
	cd $(BACKEND) && $(PY) scripts/export_openapi.py --check

openapi-write: ## 重写 OpenAPI 快照（改路由/Schema 后执行并提交）
	cd $(BACKEND) && $(PY) scripts/export_openapi.py --write

check: lint-backend format-check-backend openapi-check test-backend ## 复刻 CI 后端 job 的质量门禁

check-ui: lint-ui format-check-ui ## 复刻 CI 前端 job 的质量门禁（需已安装依赖）

##@ 前端

ui-install: install-ui ## install-ui 的别名

ui-dev: ## 启动租户工作台 dev server（:3000）
	cd $(ROOT)/ui/workbench && npm run dev

ui-dev-admin: ## 启动运营后台 dev server（:3001）
	cd $(ROOT)/ui/admin && npm run dev

ui-build: ## 构建两个前端（产物部署到 OSS）
	cd $(ROOT)/ui/workbench && npm run build
	cd $(ROOT)/ui/admin && npm run build

##@ Docker 镜像

build-api: ## 构建 API 镜像到本地（--load）
	@$(call buildx_cmd,milesai-api,Dockerfile.api,--load)

build-worker: ## 构建 Worker/Beat 镜像到本地（--load）
	@$(call buildx_cmd,milesai-worker,Dockerfile.worker,--load)

build-mcp-runner: ## 构建 MCP Runner 镜像到本地（--load）
	@$(call buildx_cmd,milesai-mcp-runner,Dockerfile.mcp-runner,--load)

build-all: build-api build-worker build-mcp-runner ## 构建全部镜像到本地

push-api: ## 构建并推送 API 镜像
	@$(call buildx_cmd,milesai-api,Dockerfile.api,--push)

push-worker: ## 构建并推送 Worker/Beat 镜像
	@$(call buildx_cmd,milesai-worker,Dockerfile.worker,--push)

push-mcp-runner: ## 构建并推送 MCP Runner 镜像
	@$(call buildx_cmd,milesai-mcp-runner,Dockerfile.mcp-runner,--push)

push-all: push-api push-worker push-mcp-runner ## 构建并推送全部镜像

##@ 清理

clean: ## 清理 Python 与前端构建缓存
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(ROOT)/ui/workbench/.next $(ROOT)/ui/admin/.next
	@echo "已清理 __pycache__ 与 .next"
