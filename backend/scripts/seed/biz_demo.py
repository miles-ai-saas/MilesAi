"""业务中心演示数据：客户、商机、项目、交付、合同、供应商等（幂等）。"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.biz import (
    BizClient,
    BizClientContact,
    BizContract,
    BizDeliverable,
    BizMilestone,
    BizOpportunity,
    BizPayment,
    BizProject,
    BizProjectMember,
    BizProjectSupplier,
    BizQuote,
    BizSupplier,
    BizSupplierContact,
    BizWorkPackage,
)
from app.models.platform.tenant import Tenant
from app.models.platform.user import User
from scripts.seed.biz import DEFAULT_SERVICE_LINE_STAGES

DEMO_CLIENT_SHORT = "demo-hailan"


async def _tenant_admin(session: AsyncSession) -> tuple | None:
    settings = get_settings()
    tenant_id = await session.scalar(
        select(Tenant.id).where(Tenant.name == settings.seed_tenant_name).limit(1)
    )
    if not tenant_id:
        return None
    admin = await session.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.username == settings.seed_admin_username,
        ).limit(1)
    )
    if not admin:
        return None
    return tenant_id, admin


def _stage(service_line: str, index: int) -> tuple[str | None, int]:
    names = DEFAULT_SERVICE_LINE_STAGES.get(service_line, [])
    if not names or index >= len(names):
        return None, index
    return names[index], index


async def seed_biz_demo_data(session: AsyncSession) -> None:
    """为默认租户写入一套可跑通业务中心各页面的演示数据。"""
    ctx = await _tenant_admin(session)
    if not ctx:
        return
    tenant_id, admin = ctx

    if await session.scalar(
        select(BizClient.id).where(
            BizClient.tenant_id == tenant_id,
            BizClient.short_name == DEMO_CLIENT_SHORT,
        )
    ):
        return

    today = date.today()

    # ── 客户 ──
    c_hailan = BizClient(
        tenant_id=tenant_id,
        name="海岚文旅集团",
        short_name=DEMO_CLIENT_SHORT,
        industry="tourism",
        confidentiality_level="normal",
        address="杭州市西湖区文旅大道 88 号",
        remark="演示客户 · 展览与品牌项目",
        created_by=admin.id,
    )
    c_yunchuang = BizClient(
        tenant_id=tenant_id,
        name="云创科技股份有限公司",
        short_name="demo-yunchuang",
        industry="enterprise",
        confidentiality_level="internal",
        address="上海市浦东新区科创路 1 号",
        remark="演示客户 · 内部级脱敏演练",
        created_by=admin.id,
    )
    c_gov = BizClient(
        tenant_id=tenant_id,
        name="某市宣传部",
        short_name="demo-gov",
        industry="government",
        confidentiality_level="restricted",
        address="（演示地址）",
        remark="演示客户 · 涉密不可案例入库",
        created_by=admin.id,
    )
    c_park = BizClient(
        tenant_id=tenant_id,
        name="未来产业园区管理办公室",
        short_name="demo-park",
        industry="park",
        confidentiality_level="normal",
        created_by=admin.id,
    )
    session.add_all([c_hailan, c_yunchuang, c_gov, c_park])
    await session.flush()

    session.add_all([
        BizClientContact(
            tenant_id=tenant_id, client_id=c_hailan.id, name="林婉清", title="品牌总监",
            phone="13800001001", email="lin@hailan-demo.local", is_primary=True,
        ),
        BizClientContact(
            tenant_id=tenant_id, client_id=c_yunchuang.id, name="周航", title="市场副总裁",
            phone="13800002001", email="zhou@yunchuang-demo.local", is_primary=True,
        ),
        BizClientContact(
            tenant_id=tenant_id, client_id=c_gov.id, name="联系人 A", title="宣传处",
            phone="0571-88880000", is_primary=True,
        ),
    ])
    await session.flush()

    # ── 商机 ──
    opp_won = BizOpportunity(
        tenant_id=tenant_id, client_id=c_hailan.id,
        name="2026 城市品牌展陈项目",
        code="OPP-DEMO-001", stage="won",
        expected_value=680_000, probability=100,
        expected_close_date=today - timedelta(days=30),
        owner_id=admin.id, created_by=admin.id,
    )
    opp_pipe = BizOpportunity(
        tenant_id=tenant_id, client_id=c_park.id,
        name="园区文创市集活动",
        code="OPP-DEMO-002", stage="proposal",
        expected_value=120_000, probability=60,
        expected_close_date=today + timedelta(days=45),
        owner_id=admin.id, created_by=admin.id,
    )
    opp_neg = BizOpportunity(
        tenant_id=tenant_id, client_id=c_yunchuang.id,
        name="云创品牌视觉升级",
        code="OPP-DEMO-003", stage="negotiation",
        expected_value=350_000, probability=75,
        expected_close_date=today + timedelta(days=20),
        owner_id=admin.id, created_by=admin.id,
    )
    session.add_all([opp_won, opp_pipe, opp_neg])
    await session.flush()

    session.add(BizQuote(
        tenant_id=tenant_id, opportunity_id=opp_neg.id, client_id=c_yunchuang.id,
        name="品牌升级报价 v2", amount=348_000, status="sent", version="v2",
        valid_until=today + timedelta(days=30), created_by=admin.id,
    ))

    # ── 项目 ──
    p_exhibition = BizProject(
        tenant_id=tenant_id, client_id=c_hailan.id, opportunity_id=opp_won.id,
        code="PJ-DEMO-001", name="2026 城市品牌展",
        status="active", total_budget=680_000,
        description="主展陈 + 品牌叙事空间，含效果图与落地搭建。",
        owner_id=admin.id, start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=90), created_by=admin.id,
    )
    p_event = BizProject(
        tenant_id=tenant_id, client_id=c_yunchuang.id,
        code="PJ-DEMO-002", name="云创 2026 年度峰会",
        status="active", total_budget=420_000,
        description="方案、执行与复盘全案。",
        owner_id=admin.id, start_date=today - timedelta(days=20),
        end_date=today + timedelta(days=40), created_by=admin.id,
    )
    p_restricted = BizProject(
        tenant_id=tenant_id, client_id=c_gov.id,
        code="PJ-DEMO-003", name="城市形象宣传短片",
        status="active", total_budget=280_000,
        description="涉密演示项目，禁止案例入库。",
        owner_id=admin.id, created_by=admin.id,
    )
    session.add_all([p_exhibition, p_event, p_restricted])
    await session.flush()

    opp_won.converted_to_project_id = p_exhibition.id

    ex_stage, ex_idx = _stage("exhibition", 2)
    ev_stage, ev_idx = _stage("event", 1)
    vi_stage, vi_idx = _stage("video_production", 0)

    wp_ex = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_exhibition.id,
        service_line="exhibition", name="主展陈工作包",
        stage=ex_stage, stage_index=ex_idx,
        status="in_progress", budget=450_000, actual_cost=180_000,
        owner_id=admin.id,
        planned_start=today - timedelta(days=45),
        planned_end=today + timedelta(days=60),
    )
    wp_ev = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_event.id,
        service_line="event", name="峰会执行包",
        stage=ev_stage, stage_index=ev_idx,
        status="review", budget=280_000, actual_cost=95_000,
        owner_id=admin.id,
    )
    wp_vi = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_restricted.id,
        service_line="video_production", name="宣传片摄制",
        stage=vi_stage, stage_index=vi_idx,
        status="in_progress", budget=260_000,
        owner_id=admin.id,
    )
    wp_sign = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_exhibition.id,
        service_line="signage", name="导视系统",
        stage=_stage("signage", 0)[0], stage_index=0,
        status="pending", budget=80_000,
        owner_id=admin.id,
    )
    session.add_all([wp_ex, wp_ev, wp_vi, wp_sign])
    await session.flush()

    session.add(BizProjectMember(
        tenant_id=tenant_id, project_id=p_exhibition.id,
        user_id=admin.id, role_in_project="owner",
    ))

    session.add_all([
        BizMilestone(
            tenant_id=tenant_id, project_id=p_exhibition.id, work_package_id=wp_ex.id,
            title="效果图客户确认", due_date=today + timedelta(days=3), sort_order=1,
        ),
        BizMilestone(
            tenant_id=tenant_id, project_id=p_exhibition.id, work_package_id=wp_ex.id,
            title="施工图提交", due_date=today - timedelta(days=2), sort_order=2,
        ),
        BizMilestone(
            tenant_id=tenant_id, project_id=p_event.id, work_package_id=wp_ev.id,
            title="场地搭建完成", due_date=today + timedelta(days=7), sort_order=1,
        ),
    ])

    session.add_all([
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_exhibition.id, work_package_id=wp_ex.id,
            name="空间效果图 v1", type="document", status="submitted", version="v1.0",
            submitted_at=f"{today.isoformat()}T10:00:00Z", created_by=admin.id,
        ),
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_exhibition.id, work_package_id=wp_ex.id,
            name="展陈叙事脚本", type="document", status="accepted", version="v2.0",
            submitted_at=f"{(today - timedelta(days=5)).isoformat()}T10:00:00Z",
            accepted_at=f"{(today - timedelta(days=3)).isoformat()}T15:00:00Z",
            created_by=admin.id,
        ),
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_exhibition.id,
            name="比选方案草稿", type="document", status="draft", version="v0.9",
            created_by=admin.id,
        ),
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_event.id, work_package_id=wp_ev.id,
            name="活动流程表", type="document", status="submitted", version="v1",
            submitted_at=f"{today.isoformat()}T09:00:00Z", created_by=admin.id,
        ),
    ])

    # ── 合同与收付款 ──
    ctr_ex = BizContract(
        tenant_id=tenant_id, project_id=p_exhibition.id, client_id=c_hailan.id,
        name="2026 城市品牌展服务合同", contract_no="CTR-DEMO-001",
        type="service", status="active", total_amount=680_000,
        signed_date=today - timedelta(days=55),
        start_date=today - timedelta(days=55), end_date=today + timedelta(days=120),
        payment_terms="签约 30% · 中期 40% · 验收 30%",
        created_by=admin.id,
    )
    ctr_ev = BizContract(
        tenant_id=tenant_id, project_id=p_event.id, client_id=c_yunchuang.id,
        name="云创峰会执行合同", contract_no="CTR-DEMO-002",
        type="service", status="signed", total_amount=420_000,
        payment_terms="预付 50% · 活动结束后 50%",
        created_by=admin.id,
    )
    session.add_all([ctr_ex, ctr_ev])
    await session.flush()

    session.add_all([
        BizPayment(
            tenant_id=tenant_id, contract_id=ctr_ex.id, project_id=p_exhibition.id,
            name="签约款 30%", direction="in", amount=204_000, status="paid",
            planned_date=today - timedelta(days=50), paid_date=today - timedelta(days=48),
            method="银行转账", created_by=admin.id,
        ),
        BizPayment(
            tenant_id=tenant_id, contract_id=ctr_ex.id, project_id=p_exhibition.id,
            name="中期款 40%", direction="in", amount=272_000, status="pending",
            planned_date=today + timedelta(days=14), method="银行转账", created_by=admin.id,
        ),
        BizPayment(
            tenant_id=tenant_id, contract_id=ctr_ex.id, project_id=p_exhibition.id,
            name="搭建外包预付款", direction="out", amount=80_000, status="pending",
            planned_date=today + timedelta(days=7), method="银行转账", created_by=admin.id,
        ),
        BizPayment(
            tenant_id=tenant_id, contract_id=ctr_ev.id, project_id=p_event.id,
            name="活动预付 50%", direction="in", amount=210_000, status="pending",
            planned_date=today + timedelta(days=10), created_by=admin.id,
        ),
    ])

    # ── 供应商 ──
    s_build = BizSupplier(
        tenant_id=tenant_id, name="华东展览搭建有限公司", short_name="华东搭建",
        category="construction", status="active",
        contact_name="马工", contact_phone="13900003001",
        address="苏州市工业园区", created_by=admin.id,
    )
    s_video = BizSupplier(
        tenant_id=tenant_id, name="锐视影视工作室", short_name="锐视",
        category="video", status="active",
        contact_name="陈导", contact_phone="13900004001", created_by=admin.id,
    )
    s_print = BizSupplier(
        tenant_id=tenant_id, name="快印文化传媒", short_name="快印",
        category="print", status="active",
        contact_name="刘经理", created_by=admin.id,
    )
    session.add_all([s_build, s_video, s_print])
    await session.flush()

    session.add(BizSupplierContact(
        tenant_id=tenant_id, supplier_id=s_build.id,
        name="马工", title="项目经理", phone="13900003001", is_primary=True,
    ))

    session.add_all([
        BizProjectSupplier(
            tenant_id=tenant_id, project_id=p_exhibition.id, supplier_id=s_build.id,
            work_package_id=wp_ex.id, role_description="展陈搭建",
            contracted_amount=120_000, status="active",
        ),
        BizProjectSupplier(
            tenant_id=tenant_id, project_id=p_restricted.id, supplier_id=s_video.id,
            work_package_id=wp_vi.id, role_description="拍摄制作",
            contracted_amount=180_000, status="active",
        ),
    ])

    await session.flush()
