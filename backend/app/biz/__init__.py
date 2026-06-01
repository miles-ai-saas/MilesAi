"""业务中心——租户项目制交付（广告公司试点）。
与 app/tenant 同为 L0/L1，挂载同一 /api/v1 与 JWT。

子域：clients / projects / work_packages / deliverables / dashboard。
ORM 定义在 app/models/biz/，由 registry 注册到 Alembic。
"""
