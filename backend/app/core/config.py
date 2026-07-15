"""全局配置（环境变量 / .env），供 API、Worker、RAG 解析与向量库共用。"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env（本地开发）优先，其次项目根 .env（Docker Compose）
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (
    _BACKEND_DIR / ".env",
    _PROJECT_ROOT / ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_FILES if p.exists()] or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MilesAi"
    app_description: str = "一体化 AI 智能编排与 RAG 应用平台 REST API"
    app_env: str = "development"
    debug: bool = True
    # 应用日志级别：DEBUG | INFO | WARNING | ERROR（见 app.core.logging）
    log_level: str = "INFO"
    # HTTP 访问日志中间件（见 app.middlewares.access_log）
    log_http_access: bool = True
    secret_key: str = "change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    agent_api_debug_token_ttl_hours: int = 24

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "milesai"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    langgraph_redis_db: int = 0
    langgraph_redis_checkpoint: bool = True

    # 对象存储：S3 兼容 API（MinIO / OSS / AWS S3 等）
    object_storage_backend: str = "s3"
    object_storage_endpoint: str = "localhost:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "milesai"
    object_storage_secure: bool = False
    object_storage_region: str = ""

    # 向量存储：weaviate | milvus | pgvector（均经 LangChain 集成）
    vector_store_backend: str = "weaviate"
    weaviate_host: str = "localhost"
    weaviate_port: int = 8080
    weaviate_scheme: str = "http"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_db_name: str = "default"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    # 全局任务超时（秒）：soft 触发 SoftTimeLimitExceeded；hard 强制终止 Worker 子进程
    celery_task_soft_time_limit_sec: int = 3600
    celery_task_time_limit_sec: int = 3660
    celery_ingest_soft_time_limit_sec: int = 1800
    celery_ingest_time_limit_sec: int = 1860
    celery_generative_soft_time_limit_sec: int = 7200
    celery_generative_time_limit_sec: int = 7260

    # 生视频：True 时工具/流程节点提交 Celery 异步任务；False 时同步阻塞（调试）
    generative_video_async: bool = True
    # 生图：True 时工具/流程节点提交 Celery 异步任务；False 时同步阻塞（调试）
    generative_image_async: bool = True

    # 工作台智能体对话 WebSocket（关闭时前端回退 HTTP POST /chat）
    agent_chat_websocket_enabled: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:3002,http://127.0.0.1:3002"

    # MCP 出站：生产建议 false，禁止连接本机/内网（防 SSRF）
    mcp_allow_private_hosts: bool = True

    # MCP Runner（STDIO 沙箱）：独立服务，API 不 subprocess 用户命令
    mcp_runner_enabled: bool = False
    mcp_runner_url: str = "http://localhost:8090"
    mcp_runner_token: str = ""
    mcp_runner_max_concurrent_per_tenant: int = 3
    mcp_runner_command_whitelist: str = "npx,node,python,python3"

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_admin_email: str = "admin@local.dev"
    seed_tenant_name: str = "默认租户"
    seed_platform_admin_username: str = "platform"
    seed_platform_admin_password: str = "admin123"

    # 应用市场审核：platform（SaaS 默认）| tenant | off
    marketplace_review_mode: str | None = None
    marketplace_review_tenant_id: str | None = None
    # designated：仅 MARKETPLACE_REVIEW_TENANT_ID 可审；publisher：仅发布方租户可审
    marketplace_review_scope: str = "designated"

    # local：Sentence-Transformers；litellm：云端 embedding API（如 dashscope/text-embedding-v4）
    embedding_backend: str = "local"
    embedding_model_name: str = "BAAI/bge-base-zh-v1.5"
    embedding_litellm_model: str = "dashscope/text-embedding-v4"
    embedding_litellm_api_key: str = ""
    embedding_litellm_api_base: str | None = None
    # LiteLLM 日志级别（默认 ERROR，避免未安装 botocore 时的 Bedrock/SageMaker 预加载警告）
    litellm_log: str = "ERROR"
    # 新建知识库写入的向量维度（local BGE=768；dashscope v3 等常用 1024）
    embedding_vector_dimension: int = 768
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50

    # SMTP 邮件告警（可选）
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "milesai@localhost"
    smtp_tls: bool = True

    # 技能包文件根目录（相对 backend 目录或绝对路径）
    skills_data_root: str = ".data/skills"

    # 解析：pypdf（默认）| docling（需 milesai[parse-docling]）；见 app.rag.parse.loaders
    parse_pdf_backend: str = "pypdf"
    # docling 失败或未安装时，PDF 是否回退 pypdf（Office 无 docling 则直接报错）
    parse_docling_fallback_pypdf: bool = True

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def database_url_sync(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def langgraph_redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.langgraph_redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.langgraph_redis_db}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def APP_DESCRIPTION(self) -> str:
        return self.app_description

    @property
    def DEBUG(self) -> bool:
        return self.debug

    @property
    def weaviate_url(self) -> str:
        return f"{self.weaviate_scheme}://{self.weaviate_host}:{self.weaviate_port}"

    @property
    def mcp_runner_command_whitelist_set(self) -> frozenset[str]:
        return frozenset(c.strip() for c in self.mcp_runner_command_whitelist.split(",") if c.strip())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    os.environ.setdefault("LITELLM_LOG", settings.litellm_log.upper())
    return settings
