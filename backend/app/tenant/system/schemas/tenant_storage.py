"""租户 BYOK 对象存储配置模型。"""

from uuid import UUID

from pydantic import BaseModel, Field


# 租户对象存储配置输出（secret 脱敏展示）。
class TenantObjectStorageOut(BaseModel):
    tenant_id: UUID = Field(description="租户 ID")
    is_enabled: bool = Field(description="是否启用租户自有对象存储")
    endpoint: str = Field(default="", description="S3 兼容 endpoint（host:port）")
    bucket: str = Field(default="", description="存储桶名称")
    access_key: str = Field(default="", description="Access Key")
    secret_key_masked: str | None = Field(default=None, description="Secret Key 脱敏展示")
    secure: bool = Field(default=False, description="HTTPS")
    region: str | None = Field(default=None, description="区域（可选）")
    source: str = Field(description="platform | tenant")


# 对象存储配置写入请求（secret_key 留空表示沿用已存密钥）。
class TenantObjectStorageUpsert(BaseModel):
    is_enabled: bool = Field(description="启用后新上传走租户桶")
    endpoint: str = Field(default="", max_length=255, description="endpoint")
    bucket: str = Field(default="", max_length=128, description="bucket")
    access_key: str = Field(default="", max_length=128, description="access key")
    secret_key: str | None = Field(
        default=None,
        description="secret key；留空表示不修改已保存密钥",
    )
    secure: bool = Field(default=False, description="HTTPS")
    region: str | None = Field(default=None, max_length=64, description="region")


# 对象存储连接测试结果。
class TenantObjectStorageTestResult(BaseModel):
    ok: bool = Field(description="探测是否成功")
    message: str = Field(description="说明")
