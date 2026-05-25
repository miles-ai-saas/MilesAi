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
    secret_key: str = "change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

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
    object_storage_region: str | None = None

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

    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:3002,http://127.0.0.1:3002"
    )

    # MCP 出站：生产建议 false，禁止连接本机/内网（防 SSRF）
    mcp_allow_private_hosts: bool = True

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_admin_email: str = "admin@local.dev"
    seed_tenant_name: str = "默认租户"
    seed_platform_admin_username: str = "platform"
    seed_platform_admin_password: str = "admin123"

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

    # 技能包文件根目录（相对 backend 目录或绝对路径）
    skills_data_root: str = ".data/skills"

    # 解析：pypdf（默认）| docling（需 milesai[parse-docling]）；见 app.rag.parse.loaders
    parse_pdf_backend: str = "pypdf"
    # docling 失败或未安装时，PDF 是否回退 pypdf（Office 无 docling 则直接报错）
    parse_docling_fallback_pypdf: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def langgraph_redis_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}@{self.redis_host}:"
                f"{self.redis_port}/{self.langgraph_redis_db}"
            )
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

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    os.environ.setdefault("LITELLM_LOG", settings.litellm_log.upper())
    return settings
