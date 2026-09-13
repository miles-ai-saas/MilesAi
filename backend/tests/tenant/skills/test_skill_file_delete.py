"""技能包文件删除 API（storage + service 逻辑）。"""

from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.skills.storage import SKILL_MD_FILENAME, delete_file, write_file


@pytest.fixture
def skill_dir(tmp_path, monkeypatch):
    tid = uuid4()
    slug = "demo"

    def _dir(tid_arg, s):
        return tmp_path / str(tid_arg) / s

    monkeypatch.setattr("miles_portal.tenant.skills.storage.skill_package_dir", _dir)
    base = _dir(tid, slug)
    base.mkdir(parents=True)
    (base / SKILL_MD_FILENAME).write_text("---\nname: x\n---\n", encoding="utf-8")
    write_file(tid, slug, "references/a.md", "x")
    return tid, slug


def test_delete_file_ok(skill_dir):
    tid, slug = skill_dir
    delete_file(tid, slug, "references/a.md")
    with pytest.raises(FileNotFoundError):
        delete_file(tid, slug, "references/a.md")


def test_delete_skill_md_forbidden(skill_dir):
    tid, slug = skill_dir
    with pytest.raises(ValueError, match=r"SKILL\.md"):
        delete_file(tid, slug, SKILL_MD_FILENAME)


@pytest.mark.asyncio
async def test_delete_file_content_service(skill_dir, monkeypatch):
    from miles_portal.tenant.skills.services.skill import SkillService

    tid, slug_name = skill_dir
    row_id = uuid4()

    row = type(
        "_Row",
        (),
        {"id": row_id, "tenant_id": tid, "slug": slug_name, "config": {}},
    )()
    svc = SkillService(db=None, ctx=type("_Ctx", (), {"tenant_id": tid})())  # type: ignore[arg-type]

    async def _get(_id):
        return row

    async def _refresh(_row):
        return None

    monkeypatch.setattr(svc, "_get_or_raise", _get)
    monkeypatch.setattr(svc, "_refresh_layout", _refresh)

    await svc.delete_file_content(row_id, "references/a.md")
    with pytest.raises(BadRequestError):
        await svc.delete_file_content(row_id, SKILL_MD_FILENAME)
