"""技能包 ZIP 导入的归档体积与条目数上限（解压炸弹 / inode 耗尽防护）。

背景：上传体积上限（100MB）只约束**压缩后**大小，解压后体积不受约束 ——
一个几百 KB 的 zip 可膨胀到数十 GB 写满磁盘。条目数同理（inode 耗尽）。

实测厘清的边界（决定守卫可以只信中央目录的声明值）：

- ``zipfile`` 会按中央目录声明的 ``file_size`` 截断读取；若实际数据与之不符，
  **抛 ``BadZipFile``**（CRC 校验）而非静默多写 —— 故「按声明值求和」是可靠上界，
  谎报尺寸者会被拒绝而不是绕过；
- 路径穿越（``../`` / 绝对路径）与符号链接成员由 ``zipfile`` 自行净化，无需额外守卫；
- ``BadZipFile`` **不是** ``AppError``，不捕获会以 500 返回，故须转成 400。

上限值通过 ``monkeypatch`` 收小，使测试无需真的构造 500MB 归档。
"""

from __future__ import annotations

import io
import struct
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.skills.services import import_service
from miles_portal.tenant.skills.services.import_service import SkillImportService


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def service():
    """绕开分类校验；``_import_dirs`` 由各用例按需替换。"""
    svc = SkillImportService(db=None, ctx=None)
    svc._cat = SimpleNamespace(validate_category_for_domain=AsyncMock(return_value=None))
    return svc


@pytest.fixture
def tiny_limits(monkeypatch):
    """把两个上限收小，便于用极小归档触发。

    ``raising=False``：上限常量尚未定义时也应让失败落在断言上，而不是 fixture 里
    抛 ``AttributeError`` —— 否则「红」的原因会被掩盖。
    """
    monkeypatch.setattr(import_service, "_MAX_ZIP_UNCOMPRESSED_BYTES", 1024, raising=False)
    monkeypatch.setattr(import_service, "_MAX_ZIP_ENTRIES", 3, raising=False)


async def test_import_zip_rejects_oversized_uncompressed(service, tiny_limits, monkeypatch):
    """解压后总体积超限应 400，且**在解压前**即拒绝（不落地任何文件）。"""
    extracted: list[object] = []
    monkeypatch.setattr(zipfile.ZipFile, "extractall", lambda self, *a, **k: extracted.append(a))

    payload = _zip_bytes({"skills/demo/SKILL.md": b"A" * 4096})
    with pytest.raises(BadRequestError, match="解压后"):
        await service.import_zip(uuid4(), payload, "demo.zip", overwrite_existing=False)

    assert extracted == [], "超限归档不应进入解压阶段（否则已有部分文件落地）"


async def test_import_zip_rejects_lying_central_directory_size(service):
    """中央目录谎报超大尺寸应在解压前被拒（守卫只信声明值）。

    与「谎报**偏小**」相对：后者由 ``zipfile`` 的 CRC 校验拒绝（``BadZipFile``），
    两者合起来才说明「只信声明值」是可靠上界。

    本用例不 monkeypatch 上限，故同时验证**生产常量**确实生效。声明值取 600MB：
    超过生产上限（500MB），而又能装进 zip 标准的 4 字节尺寸字段（>4GB 才需 ZIP64；
    ZIP64 尺寸经 ``ZipInfo.file_size`` 同样可见，故守卫无需特判）。
    """
    raw = bytearray(_zip_bytes({"skills/demo/SKILL.md": b"x"}))
    idx = raw.rindex(b"PK\x01\x02")
    struct.pack_into("<I", raw, idx + 24, 600 * 1024 * 1024)

    with pytest.raises(BadRequestError, match="解压后"):
        await service.import_zip(uuid4(), bytes(raw), "demo.zip", overwrite_existing=False)


async def test_production_zip_limits_are_coherent():
    """生产上限须自洽：解压后上限必须大于上传上限，否则正常包会被一律拒绝。"""
    assert import_service._MAX_ZIP_UNCOMPRESSED_BYTES > import_service._MAX_ZIP_BYTES
    assert import_service._MAX_ZIP_ENTRIES > 0


async def test_import_zip_rejects_too_many_entries(service, tiny_limits):
    """条目数超限应 400。"""
    members = {f"skills/demo/f{i}.txt": b"x" for i in range(5)}
    with pytest.raises(BadRequestError, match="文件数"):
        await service.import_zip(uuid4(), _zip_bytes(members), "demo.zip", overwrite_existing=False)


async def test_import_zip_rejects_corrupt_archive_as_bad_request(service):
    """非 zip / 损坏归档应 400，而非未捕获的 BadZipFile（500）。"""
    with pytest.raises(BadRequestError, match="有效的 zip"):
        await service.import_zip(uuid4(), b"definitely not a zip", "demo.zip", overwrite_existing=False)


async def test_import_zip_accepts_archive_within_limits(service, monkeypatch):
    """限额内应正常走到技能目录发现（证明守卫未误杀）。"""
    svc_import = AsyncMock(return_value="IMPORTED")
    monkeypatch.setattr(service, "_import_dirs", svc_import)

    payload = _zip_bytes({"skills/demo/SKILL.md": b"---\nname: Demo\n---\n"})
    result = await service.import_zip(uuid4(), payload, "demo.zip", overwrite_existing=False)

    assert result == "IMPORTED"
    svc_import.assert_awaited_once()
