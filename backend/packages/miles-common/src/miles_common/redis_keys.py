"""Redis Key 命名规范，避免魔法字符串散落。"""

from uuid import UUID


class RedisKeys:
    """集中管理 Redis 键前缀，避免散落魔法字符串。"""

    @staticmethod
    def session(user_id: UUID | str) -> str:
        """租户登录 access 会话（AuthService.login）。"""
        return f"session:{user_id}"

    @staticmethod
    def user_session_index(user_id: UUID | str) -> str:
        """用户多设备会话 jti 索引（SET）。"""
        return f"sessions:user:{user_id}"

    @staticmethod
    def user_session_entry(user_id: UUID | str, jti: str) -> str:
        """单条会话元数据（JSON）。"""
        return f"session:entry:{user_id}:{jti}"

    @staticmethod
    def admin_session(admin_id: UUID | str) -> str:
        """运营后台 admin_access 会话（AdminAuthService.login）。"""
        return f"admin:session:{admin_id}"

    @staticmethod
    def admin_session_scan_pattern() -> str:
        """SCAN 运营会话键（list_sessions）。"""
        return "admin:session:*"

    @staticmethod
    def token_blacklist(jti: str) -> str:
        """预留：登出后拉黑 access jti。"""
        return f"token:blacklist:{jti}"

    @staticmethod
    def api_cache(namespace: str, key_hash: str) -> str:
        """预留：API 响应缓存。"""
        return f"cache:api:{namespace}:{key_hash}"

    @staticmethod
    def ingest_lock(file_id: UUID | str) -> str:
        """预留：同一文件并发入库互斥。"""
        return f"lock:ingest:{file_id}"

    @staticmethod
    def rate_limit(tenant_id: UUID | str, api: str) -> str:
        """预留：租户级 API 限流计数。"""
        return f"ratelimit:{tenant_id}:{api}"

    @staticmethod
    def tenant_prefix(tenant_id: UUID | str) -> str:
        """租户隔离缓存命名空间前缀。"""
        return f"t:{tenant_id}:"

    @staticmethod
    def generative_job_progress(tenant_id: UUID | str, job_id: UUID | str) -> str:
        """生成任务进度 Pub/Sub 频道（租户隔离）。"""
        return f"generative:job:{tenant_id}:{job_id}"

    @staticmethod
    def a2a_push_notification_configs(tenant_id: UUID | str, task_id: UUID | str) -> str:
        """A2A 任务推送配置 HASH（field=configId, value=JSON）。"""
        return f"a2a:pushcfg:{tenant_id}:{task_id}"

    @staticmethod
    def agent_kv(tenant_id: UUID | str, key: str) -> str:
        """智能体内置 ``redis_kv`` 工具的租户隔离键（相对 key 已校验）。"""
        return f"agent_kv:{tenant_id}:{key}"

    @staticmethod
    def tokens_month_reset(period_yyyy_mm: str) -> str:
        """本月 Token 清零幂等标记（UTC ``YYYY-MM``）。"""
        return f"quota:tokens_month_reset:{period_yyyy_mm}"

    @staticmethod
    def tokens_threshold_alert(tenant_id: UUID | str, period_yyyy_mm: str, warn_percent: int) -> str:
        """本月 Token 阈值告警幂等标记（每租户每账期每阈值一次）。"""
        return f"quota:tokens_threshold_alert:{tenant_id}:{period_yyyy_mm}:{int(warn_percent)}"
