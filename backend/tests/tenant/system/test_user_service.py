"""``UserService`` 审计与批量操作的征化测试（重构前锁定行为）。

核心不变量：8 处 ``write_tenant_audit_log`` 调用都必须携带
``resource_type="user"`` 且 ``resource_id == str(user.id)``。该三元组（租户、
资源类型、资源 ID）是审计检索的依据，任何一处漂移都会让审计查询漏记录。
另有 3 处共用同一 ``action="user.update"``，仅 ``detail`` 不同。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from miles_core.tenant import TenantContext
from miles_portal.tenant.system.services import user as user_mod


def _ctx(tenant_id, *, user_id=None, is_superuser=False) -> TenantContext:
    return TenantContext(
        user_id=user_id or uuid4(),
        tenant_id=tenant_id,
        username="op",
        is_superuser=is_superuser,
        permissions=frozenset(),
    )


def _user(tenant_id, **overrides) -> SimpleNamespace:
    base = dict(
        id=uuid4(),
        tenant_id=tenant_id,
        username="alice",
        email="alice@example.com",
        phone=None,
        is_active=True,
        is_superuser=False,
        roles=[],
        hashed_password="old",
        deleted_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeRepo:
    """UserRepository 替身：按 uid 返回预置用户，记录写入。"""

    def __init__(self, users=None, roles=None):
        self._users = {u.id: u for u in (users or [])}
        self._roles = list(roles or [])
        self.created = []
        self.updated = []
        self.unique_checked = []

    async def ensure_username_unique(self, username) -> None:  # noqa: ANN001
        self.unique_checked.append(username)

    async def create(self, **kwargs):  # noqa: ANN001
        self.created.append(kwargs)
        return _user(kwargs["tenant_id"], username=kwargs["username"], email=kwargs.get("email"), is_active=True)

    async def load_roles(self, role_ids):  # noqa: ANN001
        return list(self._roles)

    async def get_with_roles(self, uid):  # noqa: ANN001
        return self._users.get(uid)

    async def update_fields(self, user, data) -> None:  # noqa: ANN001
        self.updated.append(dict(data))
        for k, v in data.items():
            setattr(user, k, v)


@pytest.fixture
def env(monkeypatch):
    """装配 UserService + 可观测替身。"""
    audits: list[dict] = []
    revokes: list = []

    async def _write_audit(db, ctx, **kwargs):  # noqa: ANN001
        audits.append(kwargs)

    class _FakeAuth:
        def __init__(self, db, ctx) -> None:  # noqa: ANN001
            pass

        async def admin_revoke_user_sessions(self, uid) -> None:  # noqa: ANN001
            revokes.append(uid)

    monkeypatch.setattr(user_mod, "write_tenant_audit_log", _write_audit)
    monkeypatch.setattr(user_mod, "AuthService", _FakeAuth)
    monkeypatch.setattr(user_mod, "hash_password", lambda p: f"hashed:{p}")

    def build(ctx, users=None, roles=None):
        db = SimpleNamespace(flush=AsyncMockLike(), refresh=AsyncMockLike(), add=lambda obj: None)
        svc = user_mod.UserService(db, ctx)
        repo = _FakeRepo(users, roles)
        svc.repo = repo
        return SimpleNamespace(svc=svc, repo=repo, db=db, audits=audits, revokes=revokes)

    env.build = build
    env.audits = audits
    env.revokes = revokes
    return env


class AsyncMockLike:
    """记录调用的异步空操作（避免为一个 flush 引入 mock 库）。"""

    def __init__(self) -> None:
        self.calls: list = []

    async def __call__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls.append((args, kwargs))
        return None


def _audit_of(audits, action):
    matching = [a for a in audits if a["action"] == action]
    assert len(matching) == 1, f"action={action} 期望 1 条，实际 {len(matching)}"
    return matching[0]


def _assert_identity(audit, user) -> None:
    """所有审计共有的身份不变量。"""
    assert audit["resource_type"] == "user"
    assert audit["resource_id"] == str(user.id)


# --------------------------------------------------------------------------- #
# create / update
# --------------------------------------------------------------------------- #


async def test_create_user_writes_audit_with_username_detail(env):  # noqa: ANN001
    tenant_id = uuid4()
    ctx = _ctx(tenant_id)
    request = object()
    e = env.build(ctx)

    await e.svc.create_user(SimpleNamespace(username="bob", email="b@e.com", phone=None, password="pw123456", tenant_id=None, role_ids=[]), request=request)

    assert e.repo.unique_checked == ["bob"]
    audit = _audit_of(e.audits, "user.create")
    assert audit["detail"] == {"username": "bob"}
    assert audit["request"] is request
    created = e.repo.created[0]
    assert created["tenant_id"] == tenant_id
    assert created["hashed_password"] == "hashed:pw123456"


async def test_update_user_audit_records_only_set_fields(env):  # noqa: ANN001
    tenant_id = uuid4()
    user = _user(tenant_id)
    e = env.build(_ctx(tenant_id, is_superuser=True), users=[user])
    body = SimpleNamespace(model_dump=lambda exclude_unset=False: {"email": "new@e.com"})

    await e.svc.update_user(user.id, body, request=None)

    audit = _audit_of(e.audits, "user.update")
    assert audit["detail"] == {"fields": ["email"]}
    _assert_identity(audit, user)
    assert e.repo.updated == [{"email": "new@e.com"}]


async def test_update_user_missing_writes_no_audit(env):  # noqa: ANN001
    e = env.build(_ctx(uuid4(), is_superuser=True))

    with pytest.raises(NotFoundError):
        await e.svc.update_user(uuid4(), SimpleNamespace(model_dump=lambda exclude_unset=False: {}))

    assert e.audits == []


async def test_update_user_cross_tenant_writes_no_audit(env):  # noqa: ANN001
    user = _user(uuid4())
    e = env.build(_ctx(uuid4(), is_superuser=False), users=[user])

    with pytest.raises(ForbiddenError):
        await e.svc.update_user(user.id, SimpleNamespace(model_dump=lambda exclude_unset=False: {}))

    assert e.audits == []


async def test_update_user_soft_deleted_treated_as_missing(env):  # noqa: ANN001
    user = _user(uuid4(), deleted_at=object())
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    with pytest.raises(NotFoundError):
        await e.svc.update_user(user.id, SimpleNamespace(model_dump=lambda exclude_unset=False: {}))

    assert e.audits == []


# --------------------------------------------------------------------------- #
# reset_password
# --------------------------------------------------------------------------- #


async def test_reset_password_rejects_short_password_without_audit(env):  # noqa: ANN001
    user = _user(uuid4())
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    with pytest.raises(BadRequestError):
        await e.svc.reset_password(user.id, "12345")

    assert e.audits == []
    assert e.revokes == []


async def test_reset_password_audits_without_detail_and_revokes_sessions(env):  # noqa: ANN001
    user = _user(uuid4())
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    await e.svc.reset_password(user.id, "newpw123")

    audit = _audit_of(e.audits, "user.reset_password")
    assert audit.get("detail") is None  # 无 detail；下游按 {} 落库
    _assert_identity(audit, user)
    assert e.revokes == [user.id]
    assert user.hashed_password == "hashed:newpw123"


# --------------------------------------------------------------------------- #
# deactivate_user
# --------------------------------------------------------------------------- #


async def test_deactivate_self_is_rejected(env):  # noqa: ANN001
    me = uuid4()
    user = _user(uuid4(), id=me)
    e = env.build(_ctx(user.tenant_id, user_id=me, is_superuser=True), users=[user])

    with pytest.raises(BadRequestError):
        await e.svc.deactivate_user(user.id)

    assert e.audits == []


async def test_deactivate_renames_fields_and_audits(env):  # noqa: ANN001
    user = _user(uuid4(), username="carol", email="c@e.com")
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    await e.svc.deactivate_user(user.id)

    suffix = user.id.hex[:8]
    assert user.username == f"carol__deleted__{suffix}"
    assert user.email == f"deleted+{suffix}+c@e.com"
    assert user.is_active is False
    assert user.deleted_at is not None
    audit = _audit_of(e.audits, "user.deactivate")
    assert audit.get("detail") is None  # 无 detail；下游按 {} 落库
    _assert_identity(audit, user)
    assert e.revokes == [user.id]


# --------------------------------------------------------------------------- #
# batch_apply：三条分支各自写审计，detail 只在此处分化
# --------------------------------------------------------------------------- #


def _batch(action, user_ids, role_ids=None):  # noqa: ANN001
    return SimpleNamespace(action=action, user_ids=user_ids, role_ids=role_ids)


async def test_batch_apply_deactivate_action_delegates(env):  # noqa: ANN001
    user = _user(uuid4(), is_active=True)
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_apply(_batch("deactivate", [user.id]))

    assert result == {"deactivated": 1, "skipped": 0}
    assert _audit_of(e.audits, "user.deactivate")["detail"] == {"batch": True}


async def test_batch_apply_enable_writes_is_active_true(env):  # noqa: ANN001
    user = _user(uuid4(), is_active=False)
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_apply(_batch("enable", [user.id]))

    assert result == {"processed": 1, "skipped": 0, "action": "enable"}
    audit = _audit_of(e.audits, "user.update")
    assert audit["detail"] == {"batch": True, "is_active": True}
    _assert_identity(audit, user)
    assert user.is_active is True


async def test_batch_apply_enable_already_active_is_skipped_without_audit(env):  # noqa: ANN001
    user = _user(uuid4(), is_active=True)
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_apply(_batch("enable", [user.id]))

    assert result["skipped"] == 1
    assert e.audits == []


async def test_batch_apply_disable_writes_is_active_false_and_revokes(env):  # noqa: ANN001
    user = _user(uuid4(), is_active=True)
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_apply(_batch("disable", [user.id]))

    assert result["processed"] == 1
    audit = _audit_of(e.audits, "user.update")
    assert audit["detail"] == {"batch": True, "is_active": False}
    _assert_identity(audit, user)
    assert e.revokes == [user.id]


async def test_batch_apply_assign_roles_writes_role_ids(env):  # noqa: ANN001
    tenant_id = uuid4()
    user = _user(tenant_id)
    role_id = uuid4()
    roles = [SimpleNamespace(id=role_id, code="r1")]
    e = env.build(_ctx(tenant_id, is_superuser=True), users=[user], roles=roles)

    result = await e.svc.batch_apply(_batch("assign_roles", [user.id], role_ids=[role_id]))

    assert result["processed"] == 1
    audit = _audit_of(e.audits, "user.update")
    assert audit["detail"] == {"batch": True, "role_ids": [str(role_id)]}
    _assert_identity(audit, user)
    assert user.roles == roles


async def test_batch_apply_skips_self_without_audit(env):  # noqa: ANN001
    me = uuid4()
    e = env.build(_ctx(uuid4(), user_id=me, is_superuser=True))

    result = await e.svc.batch_apply(_batch("disable", [me]))

    assert result["skipped"] == 1
    assert e.audits == []


async def test_batch_apply_skips_cross_tenant_without_audit(env):  # noqa: ANN001
    user = _user(uuid4())
    e = env.build(_ctx(uuid4(), is_superuser=False), users=[user])

    result = await e.svc.batch_apply(_batch("disable", [user.id]))

    assert result["skipped"] == 1
    assert e.audits == []


async def test_batch_apply_skips_cancelled_action_silently(env):  # noqa: ANN001
    """enable/disable/assign_roles 之外的动作不处理任何用户，也不写审计。"""
    user = _user(uuid4())
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_apply(_batch("unknown", [user.id]))

    assert result == {"processed": 0, "skipped": 0, "action": "unknown"}
    assert e.audits == []


# --------------------------------------------------------------------------- #
# batch_deactivate
# --------------------------------------------------------------------------- #


async def test_batch_deactivate_audits_with_batch_detail(env):  # noqa: ANN001
    user = _user(uuid4(), username="dave", email="d@e.com", is_active=True)
    e = env.build(_ctx(user.tenant_id, is_superuser=True), users=[user])

    result = await e.svc.batch_deactivate([user.id])

    assert result == {"deactivated": 1, "skipped": 0}
    audit = _audit_of(e.audits, "user.deactivate")
    assert audit["detail"] == {"batch": True}
    _assert_identity(audit, user)
    suffix = user.id.hex[:8]
    assert user.username == f"dave__deleted__{suffix}"
    assert user.deleted_at is not None


async def test_batch_deactivate_skips_inactive_and_missing(env):  # noqa: ANN001
    inactive = _user(uuid4(), is_active=False)
    e = env.build(_ctx(uuid4(), is_superuser=True), users=[inactive])

    result = await e.svc.batch_deactivate([inactive.id, uuid4()])

    assert result == {"deactivated": 0, "skipped": 2}
    assert e.audits == []


# --------------------------------------------------------------------------- #
# 不变量：所有审计的身份字段一致
# --------------------------------------------------------------------------- #


async def test_all_audits_share_resource_type_and_id(env):  # noqa: ANN001
    """跨方法汇总：无论走哪条路径，resource_type 恒为 user、resource_id 恒为用户 ID。"""
    tenant_id = uuid4()
    active = _user(tenant_id, is_active=True)
    inactive = _user(tenant_id, is_active=False)
    e = env.build(_ctx(tenant_id, is_superuser=True), users=[active, inactive])

    await e.svc.batch_apply(_batch("enable", [inactive.id]))
    await e.svc.batch_apply(_batch("disable", [active.id]))

    assert len(e.audits) == 2
    for audit in e.audits:
        assert audit["resource_type"] == "user"
    by_id = {a["resource_id"] for a in e.audits}
    assert by_id == {str(active.id), str(inactive.id)}
    assert {a["action"] for a in e.audits} == {"user.update"}
