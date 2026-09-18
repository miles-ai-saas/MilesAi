"""技能包 ZIP 导出：磁盘目录 → 归档，且与 ``import_zip`` 的 ``skills/`` 约定往返一致。

导出之所以要落到 ``skills/{slug}/`` 一层，是因为 ``SkillImportService.import_zip``
要求解压后存在 ``skills/`` 目录（``discover_skill_dirs`` 只认其下含 SKILL.md 的子目录）。
本文件把这个「导出 → 再导入」的往返契约钉住：只断言「有 zip」不够，还要断言归档能被
导入侧的前置扫描认出来，否则导出物只能下载、不能再导入。
"""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.skills.services.skill import SkillService
from miles_portal.tenant.skills.storage import SKILL_MD_FILENAME, discover_skill_dirs


def _ctx(tenant_id) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="tester",
        is_superuser=True,
        permissions=frozenset(),
    )


class _FakeSkill:
    """仅暴露 ``SkillService._get_or_raise`` 会读到的字段。"""

    def __init__(self, tenant_id, slug: str) -> None:
        self.id = uuid4()
        self.tenant_id = tenant_id
        self.slug = slug
        self.name = "Demo"


class _FakeDb:
    def __init__(self, skill: _FakeSkill) -> None:
        self._skill = skill

    async def get(self, _model, _id):  # noqa: ANN001
        return self._skill


@pytest.fixture
def skill_dir(tmp_path, monkeypatch):
    tenant_id = uuid4()
    slug = "demo-skill"

    def _dir(tid, s):
        return tmp_path / str(tid) / s

    monkeypatch.setattr("miles_portal.tenant.skills.storage.skill_package_dir", _dir)
    monkeypatch.setattr("miles_portal.tenant.skills.skill_layout.skill_package_dir", _dir)

    base = _dir(tenant_id, slug)
    base.mkdir(parents=True)
    (base / SKILL_MD_FILENAME).write_text("---\nname: Demo\ndescription: 演示\n---\n\n正文\n", encoding="utf-8")
    (base / "references").mkdir()
    (base / "references" / "guide.md").write_text("# Guide\n细节\n", encoding="utf-8")
    (base / "scripts").mkdir()
    (base / "scripts" / "run.py").write_text("def run(params):\n    return params\n", encoding="utf-8")
    return tenant_id, slug, base


@pytest.mark.asyncio
async def test_export_zip_packages_skill_under_skills_dir(skill_dir):
    tenant_id, slug, _base = skill_dir
    skill = _FakeSkill(tenant_id, slug)
    service = SkillService(_FakeDb(skill), _ctx(tenant_id))

    filename, payload = await service.export_zip(skill.id)

    assert filename == f"{slug}.zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = set(zf.namelist())
        assert f"skills/{slug}/{SKILL_MD_FILENAME}" in names
        assert f"skills/{slug}/references/guide.md" in names
        assert f"skills/{slug}/scripts/run.py" in names
        # 文件内容原样带出
        assert "细节" in zf.read(f"skills/{slug}/references/guide.md").decode("utf-8")


@pytest.mark.asyncio
async def test_exported_zip_satisfies_import_precondition(skill_dir, tmp_path):
    """往返契约：导出物解压后，导入侧的前置扫描必须能认出技能目录。"""
    tenant_id, slug, _base = skill_dir
    skill = _FakeSkill(tenant_id, slug)
    service = SkillService(_FakeDb(skill), _ctx(tenant_id))

    _filename, payload = await service.export_zip(skill.id)

    extracted = tmp_path / "roundtrip"
    extracted.mkdir()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(extracted)

    skills_root = extracted / "skills"
    assert skills_root.is_dir(), "导出物缺少 import_zip 要求的 skills/ 目录"
    dirs = discover_skill_dirs(skills_root)
    assert [d.name for d in dirs] == [slug]
    assert (dirs[0] / SKILL_MD_FILENAME).is_file()


@pytest.mark.asyncio
async def test_export_zip_excludes_pycache_and_hidden_files(skill_dir):
    """导出不得带上 __pycache__ / 隐藏文件（它们是运行残留，不是技能内容）。"""
    tenant_id, slug, base = skill_dir
    (base / "__pycache__").mkdir()
    (base / "__pycache__" / "run.cpython-312.pyc").write_bytes(b"\x00\x01")
    (base / ".DS_Store").write_bytes(b"\x00")
    skill = _FakeSkill(tenant_id, slug)
    service = SkillService(_FakeDb(skill), _ctx(tenant_id))

    _filename, payload = await service.export_zip(skill.id)

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = zf.namelist()
    assert not [n for n in names if "__pycache__" in n]
    assert not [n for n in names if n.endswith(".DS_Store")]
    assert f"skills/{slug}/{SKILL_MD_FILENAME}" in names
