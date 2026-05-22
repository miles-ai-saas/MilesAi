-- 首次初始化 PostgreSQL 时启用 pgvector（供 VECTOR_STORE_BACKEND=pgvector 使用）
CREATE EXTENSION IF NOT EXISTS vector;
