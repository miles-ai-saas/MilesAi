"""租户技能包种子（幂等，可重复执行）。

写入 ORM，并在 ``SKILLS_DATA_ROOT/{tenant_id}/{slug}/`` 落盘完整技能目录：
``SKILL.md``、``references/``、``scripts/``（已存在的附属文件不覆盖）。
命令：``milesai seed skills``
依赖：``seed tenant``、``seed categories``。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.soft_delete import not_deleted
from miles_core.models.meta.category import CategoryDomain
from miles_portal.tenant.skills.models import SkillPackage
from miles_portal.tenant.skills.skill_layout import build_layout_index, merge_layout_into_config
from miles_portal.tenant.skills.skill_md import build_skill_md
from miles_portal.tenant.skills.storage import skill_package_dir, write_file, write_skill_md

from miles_server.scripts.seed._helpers import category_id_by_slug, list_tenant_ids

SEED_SKILL_PACKAGES: list[dict] = [
    {
        "slug": "customer_service_playbook",
        "name": "客服应答手册",
        "category_slug": "general",
        "description": "在线客服场景的标准应答结构、转人工边界与合规自检。",
        "tool_names": [],
        "body": """## 适用场景

用户咨询产品、订单、政策；情绪投诉；要求人工。

## 应答结构

1. **确认理解**：一句话复述用户诉求。
2. **解答或引导**：基于已知信息作答；不确定时说明需核实，不编造。
3. **下一步**：给出可执行动作（链接、单号、联系方式）。
4. **转人工**：涉及退款纠纷、法律威胁、媒体曝光时，收集订单号与联系方式并说明将升级。

## 合规

- 不索取密码、验证码、完整银行卡号。
- 不使用绝对化营销用语。
- 对外回复前自检事实性与敏感信息（见 `references/compliance-checklist.md`）。

## 参考与工具

- 转人工边界：`references/escalation-matrix.md`
- 发送前可用 `skill_run_script` 调用 `scripts/sanitize_reply.py` 做敏感词粗检""",
        "files": {
            "references/escalation-matrix.md": """# 转人工矩阵

| 场景 | 动作 |
|------|------|
| 退款/赔偿争议、法律威胁、媒体曝光 | 收集订单号、联系方式，说明升级专人处理 |
| 账号被盗、资金异常 | 引导官方申诉渠道，不承诺处理时限 |
| 情绪激动但可沟通 | 先共情再解答；连续 3 轮未解决可主动提供人工入口 |
| 一般咨询、物流、功能说明 | 自助解答，无需转人工 |

禁止在未核实身份时修改绑定手机/邮箱或重置密码。
""",
            "references/compliance-checklist.md": """# 对外回复合规自检

- 不索取：密码、短信验证码、完整银行卡号、身份证正反面照片
- 不承诺：绝对疗效、保本收益、未公示的赔偿金额
- 不编造：订单状态、政策条款、处理时限
- 敏感信息：脱敏展示（手机号中间四位、地址到区级）
""",
            "scripts/sanitize_reply.py": '''"""粗检回复草稿是否含高风险索取用语。"""

_FORBIDDEN = ("验证码", "密码", "银行卡号", "cvv", "身份证照片")


def run(params):
    text = str(params.get("text") or "")
    hits = [w for w in _FORBIDDEN if w in text]
    return {
        "ok": len(hits) == 0,
        "hits": hits,
        "hint": "请移除敏感索取用语后再发送" if hits else "",
    }
''',
        },
    },
    {
        "slug": "rag_qa_assistant",
        "name": "RAG 知识库问答",
        "category_slug": "general",
        "description": "绑定知识库后，指导智能体如何引用检索结果作答。",
        "tool_names": ["knowledge_search"],
        "body": """## 目标

基于知识库检索结果回答用户问题，减少幻觉。

## 步骤

1. 将用户问题整理为检索 query（可保留关键实体与约束）。
2. 调用 **knowledge_search**（或智能体已绑定的 KB 检索能力）获取片段。
3. 仅依据检索片段组织答案；片段不足时明确说明「资料中未找到」，并建议补充文档或联系管理员。
4. 回答中可标注引用来源（文档名/片段摘要），避免大段复制粘贴。

详见 `references/citation-style.md`；可用 `skill_run_script` 调用 `scripts/summarize_hits.py` 整理检索摘要。

## 输出格式

- 先给结论，再分点展开。
- 存在冲突资料时，指出冲突并给出保守建议。""",
        "files": {
            "references/citation-style.md": """# 引用格式

- 每条结论后标注来源文档名（如「来源：产品 FAQ §2」）。
- 勿大段复制；摘取 1–2 句关键句即可。
- 多来源冲突时并列列出，并给出保守结论。
""",
            "scripts/summarize_hits.py": '''"""将 knowledge_search 返回的 hits 整理为简短摘要。"""


def run(params):
    hits = params.get("hits") or []
    if not isinstance(hits, list):
        return {"error": "hits 须为列表"}
    lines = []
    for i, h in enumerate(hits[:8], 1):
        if not isinstance(h, dict):
            continue
        title = h.get("title") or h.get("source") or f"片段{i}"
        snippet = str(h.get("content") or h.get("text") or "")[:240]
        lines.append(f"{i}. {title}: {snippet}")
    return {"summary": "\\n".join(lines) if lines else "无检索结果"}
''',
        },
    },
    {
        "slug": "meeting_minutes",
        "name": "会议纪要助手",
        "category_slug": "general",
        "description": "将口语化会议记录整理为结构化纪要。",
        "tool_names": ["get_current_datetime"],
        "body": """## 输入

用户提供会议录音转写、聊天摘录或要点草稿。

## 输出结构

| 区块 | 内容 |
|------|------|
| 基本信息 | 主题、日期（可用 get_current_datetime 补全）、参与人 |
| 结论 | 3–5 条已达成结论 |
| 待办 | 负责人 + 事项 + 截止时间（未知则标 TBD） |
| 风险与遗留 | 未决问题、依赖项 |

## 风格

书面语、去口语填充词；不捏造未在原文出现的决议。

## 参考与工具

- 输出模板：`references/minutes-template.md`
- 从草稿提取待办：`skill_run_script` → `scripts/extract_action_items.py`""",
        "files": {
            "references/minutes-template.md": """# 会议纪要模板

## 基本信息
- **主题**：
- **日期**：
- **参与人**：

## 结论
1.
2.

## 待办
| 负责人 | 事项 | 截止时间 |
|--------|------|----------|
| | | TBD |

## 风险与遗留
-
""",
            "scripts/extract_action_items.py": r'''"""从自由文本中粗提取「负责人：事项」形待办行。"""

import re

_LINE = re.compile(
    r"(?P<owner>[^\s：:，,]{1,16})[：:]\s*(?P<task>.+?)(?:[，,]\s*(?:截止|ddl|by)\s*(?P<due>.+))?$",
    re.IGNORECASE,
)


def run(params):
    text = str(params.get("text") or "")
    items = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        m = _LINE.search(line)
        if m:
            items.append(
                {
                    "owner": m.group("owner"),
                    "task": m.group("task").strip(),
                    "due": (m.group("due") or "").strip() or "TBD",
                }
            )
    return {"action_items": items, "count": len(items)}
''',
        },
    },
    {
        "slug": "code_review_checklist",
        "name": "代码审查清单",
        "category_slug": "general",
        "description": "对 diff 或代码片段做结构化 Review（偏 Web 后端）。",
        "tool_names": ["calculator"],
        "body": """## 审查维度

| 级别 | 检查项 |
|------|--------|
| 严重 | 逻辑错误、注入、鉴权缺失、敏感信息硬编码 |
| 建议 | 命名、重复、边界、错误处理、测试缺口 |
| 优点 | 值得保留的实践（如有） |

## 输出

- 按文件/函数定位问题，并给出简短修改建议。
- 区分「必须修复」与「可选优化」。
- 涉及性能估算时可使用 calculator 辅助，但不替代代码阅读。
- 安全项清单见 `references/security-checklist.md`；输出格式见 `references/review-output-format.md`。
- 统计 diff 行数：`skill_run_script` → `scripts/count_diff_stats.py`。""",
        "files": {
            "references/security-checklist.md": """# 安全审查速查

- SQL/命令注入、XSS、路径穿越
- 鉴权与租户隔离（tenant_id 过滤）
- 密钥/Token 硬编码或日志泄露
- 出站 URL 未校验（SSRF）
""",
            "references/review-output-format.md": """# Review 输出格式

```markdown
## 必须修复
- `path:line` — 问题简述 — 修改建议

## 建议优化
- ...

## 亮点（可选）
- ...
```

每条须可定位到文件/符号；避免空泛批评。
""",
            "scripts/count_diff_stats.py": '''"""统计 diff 文本行数（增/删粗算）。"""


def run(params):
    diff = str(params.get("diff") or "")
    added = deleted = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return {"added_lines": added, "deleted_lines": deleted, "total": added + deleted}
''',
        },
    },
]


def _ensure_seed_files(tenant_id, slug: str, files: dict[str, str] | None) -> int:
    """仅补写缺失的 references/scripts，不覆盖用户已改文件。"""
    if not files:
        return 0
    base = skill_package_dir(tenant_id, slug)
    added = 0
    for rel, content in files.items():
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())):
            raise ValueError(f"非法种子路径: {rel}")
        if target.is_file():
            continue
        write_file(tenant_id, slug, rel, content)
        added += 1
    return added


async def _refresh_layout(session: AsyncSession, row: SkillPackage) -> None:
    layout = build_layout_index(row.tenant_id, row.slug)
    row.config = merge_layout_into_config(row.config, layout)
    await session.flush()


async def _get_or_create_skill(
    session: AsyncSession,
    tenant_id,
    *,
    slug: str,
    name: str,
    description: str | None,
    category_id,
    tool_names: list[str],
    body: str,
) -> tuple[SkillPackage, bool]:
    row = await session.scalar(
        select(SkillPackage).where(
            SkillPackage.tenant_id == tenant_id,
            SkillPackage.slug == slug,
            not_deleted(SkillPackage),
        )
    )
    if row:
        return row, False

    row = SkillPackage(
        tenant_id=tenant_id,
        category_id=category_id,
        slug=slug,
        name=name.strip(),
        description=description,
        source_type="manual",
        storage_path=slug,
        tool_names=tool_names,
        config={},
        is_active=True,
    )
    session.add(row)
    await session.flush()
    write_skill_md(
        tenant_id,
        slug,
        build_skill_md(name, description, body),
    )
    await session.refresh(row)
    return row, True


async def seed_skills_for_tenant(session: AsyncSession, tenant_id) -> tuple[int, int]:
    created = 0
    files_added = 0
    for spec in SEED_SKILL_PACKAGES:
        category_id = await category_id_by_slug(session, CategoryDomain.SKILL, spec.get("category_slug"))
        row, is_new = await _get_or_create_skill(
            session,
            tenant_id,
            slug=spec["slug"],
            name=spec["name"],
            description=spec.get("description"),
            category_id=category_id,
            tool_names=list(spec.get("tool_names") or []),
            body=spec.get("body", "").strip(),
        )
        files_added += _ensure_seed_files(tenant_id, row.slug, spec.get("files"))
        await _refresh_layout(session, row)
        if is_new:
            created += 1
    await session.flush()
    return created, files_added


async def seed_skills(session: AsyncSession) -> None:
    total_created = 0
    total_files = 0
    for tenant_id in await list_tenant_ids(session):
        created, added = await seed_skills_for_tenant(session, tenant_id)
        total_created += created
        total_files += added
    print(f">>> skills seed: created {total_created} skill package(s), added {total_files} file(s) across tenants")
