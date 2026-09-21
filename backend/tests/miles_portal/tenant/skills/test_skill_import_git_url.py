"""技能包 Git 导入：仓库地址仅允许 http(s)，阻断本地路径与内网/元数据地址。

``git clone`` 会真正发起出站连接，且能识别 ``file://`` / ``ssh://`` 等 scheme ——
若原样透传用户输入的地址，则存在本地文件读取与 SSRF 面。

判据分两层，生效条件不同（``validate_outbound_url`` 的既有语义）：

1. **scheme 限定**：只允许 ``http(s)``，**无条件生效**。这是本改动真正闭合的
   「本地文件读取」面（``file://``）。
2. **内网 / link-local 拦截**：由 ``outbound_allow_private_hosts`` 控制，而该项
   **默认 ``True``（即默认放行内网）**，为自托管场景连接内网 MCP / 存储所必需。
   故内网拦截属**运维显式收紧**后才生效的深度防御，非默认防护。

``subprocess`` 被替换为假实现：一是避免测试触网，二是让「缺少校验」时的失败形态
是「Git 克隆失败」而非校验错误 —— 断言精确到文案，才能证明校验真的在位。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core import url_security
from miles_portal.tenant.skills.services import import_service
from miles_portal.tenant.skills.services.import_service import SkillImportService


@pytest.fixture
def service(monkeypatch):
    """构造服务并绕开分类校验（本测试只关心 URL 判据）。"""
    svc = SkillImportService(db=None, ctx=None)
    svc._cat = SimpleNamespace(validate_category_for_domain=AsyncMock(return_value=None))
    monkeypatch.setattr(
        import_service,
        "subprocess",
        SimpleNamespace(run=lambda *a, **k: SimpleNamespace(returncode=1, stderr="fake-clone", stdout="")),
    )
    return svc


@pytest.fixture
def reject_private_hosts(monkeypatch):
    """显式收紧「禁止内网」（对应部署把 outbound_allow_private_hosts 设为 false）。"""
    monkeypatch.setattr(url_security, "get_settings", lambda: SimpleNamespace(outbound_allow_private_hosts=False))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ssh://git@internal.example.com/repo.git",
        "git://example.com/repo.git",
        "ftp://example.com/repo.git",
        # scp 风格：urlparse 解出 scheme=''，同样应被拒
        "git@github.com:org/repo.git",
    ],
)
async def test_import_git_rejects_non_http_scheme(service, url):
    """scheme 限定无条件生效。"""
    with pytest.raises(BadRequestError, match="仅支持 http 或 https"):
        await service.import_git(uuid4(), url, overwrite_existing=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/repo.git",
        "http://localhost/repo.git",
        "http://169.254.169.254/latest/meta-data",  # 云元数据（link-local）
    ],
)
async def test_import_git_rejects_private_hosts_when_strictened(service, reject_private_hosts, url):
    """把 outbound_allow_private_hosts 设为 false 后，内网 / link-local 亦被拒。"""
    with pytest.raises(BadRequestError, match="不允许连接"):
        await service.import_git(uuid4(), url, overwrite_existing=False)


@pytest.mark.parametrize("url", ["http://127.0.0.1/repo.git", "http://localhost/repo.git"])
async def test_import_git_private_hosts_allowed_by_default(service, url):
    """钉住默认姿态：``outbound_allow_private_hosts`` 默认 True，内网地址会放行到 clone。

    此项**不是**期望行为，而是既有默认值的显式记录 —— 若将来把默认改为 false，
    本用例会失败，提醒同步更新文档与部署说明。
    """
    with pytest.raises(BadRequestError, match="Git 克隆失败"):
        await service.import_git(uuid4(), url, overwrite_existing=False)


async def test_import_git_accepts_https_and_proceeds_to_clone(service):
    """https 通过校验后应继续走到 clone（假 clone 返回非零 → 报「Git 克隆失败」）。"""
    with pytest.raises(BadRequestError, match="Git 克隆失败"):
        await service.import_git(uuid4(), "https://github.com/org/repo.git", overwrite_existing=False)


async def test_import_git_rejects_blank_url(service):
    with pytest.raises(BadRequestError, match="不能为空"):
        await service.import_git(uuid4(), "   ", overwrite_existing=False)
