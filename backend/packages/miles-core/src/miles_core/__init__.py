"""
核心层 — 配置、安全、依赖注入、租户上下文等应用横切能力。

外部中间件连接见 miles_core.infra（db、redis、storage、vector_store）。
通用工具：纯函数见 miles_common.idgen / miles_common.redis_keys，
ORM 与健康检查见 miles_core.utils。
"""
