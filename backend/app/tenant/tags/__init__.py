"""租户全局标签域（tnt_tags + tnt_entity_tag_bindings）。

- HTTP：``/api/v1/tags``（列表/创建/删除）
- 标签在租户内跨 agent、prompt、skill、tool 共用
- 资源 API 通过 ``tag_ids`` 写入绑定；列表支持 ``tag_ids`` 筛选（OR）
- 权限：``tag:read`` / ``tag:write``
"""
