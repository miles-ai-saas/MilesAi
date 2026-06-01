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
    BizServiceLineTemplatePack,
    BizSupplier,
    BizSupplierContact,
    BizWorkPackage,
)
from app.models.biz.template_pack_status import TemplatePackStatus
from app.models.platform.tenant import Tenant
from app.models.platform.user import User
from scripts.seed.biz import DEFAULT_SERVICE_LINE_AI, DEFAULT_SERVICE_LINE_STAGES

DEMO_CLIENT_SHORT = "demo-hailan"
DEMO_EXTENDED_MARKER = "demo-retail"


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
    """为默认租户写入可跑通业务中心各页面的演示数据（分核心 / 扩展两批，均可幂等）。"""
    created_core = await _seed_biz_demo_core(session)
    created_ext = await _seed_biz_demo_extended(session)
    if created_core:
        print(">>> biz-demo seed: 核心演示数据已写入")
    if created_ext:
        print(">>> biz-demo seed: 扩展演示数据已写入")
    if not created_core and not created_ext:
        print(">>> biz-demo seed: 演示数据已存在，跳过")


async def _seed_biz_demo_core(session: AsyncSession) -> bool:
    """首批演示数据（客户 demo-hailan 等）。"""
    ctx = await _tenant_admin(session)
    if not ctx:
        print(">>> biz-demo seed: skip (no default tenant/admin)")
        return False
    tenant_id, admin = ctx

    if await session.scalar(
        select(BizClient.id).where(
            BizClient.tenant_id == tenant_id,
            BizClient.short_name == DEMO_CLIENT_SHORT,
        )
    ):
        return False

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
    return True


async def _seed_biz_demo_extended(session: AsyncSession) -> bool:
    """扩展演示数据：更多漏斗阶段、项目状态、模板市场「我的发布」等。"""
    ctx = await _tenant_admin(session)
    if not ctx:
        return False
    tenant_id, admin = ctx

    if await session.scalar(
        select(BizClient.id).where(
            BizClient.tenant_id == tenant_id,
            BizClient.short_name == DEMO_EXTENDED_MARKER,
        )
    ):
        return False

    # 扩展批次依赖核心客户（展陈项目等），若核心未 seed 则先跳过
    c_hailan = await session.scalar(
        select(BizClient).where(
            BizClient.tenant_id == tenant_id,
            BizClient.short_name == DEMO_CLIENT_SHORT,
        )
    )
    c_park = await session.scalar(
        select(BizClient).where(
            BizClient.tenant_id == tenant_id,
            BizClient.short_name == "demo-park",
        )
    )
    if not c_hailan or not c_park:
        print(">>> biz-demo seed: 扩展批次跳过（请先完成核心演示数据 seed）")
        return False

    today = date.today()

    c_retail = BizClient(
        tenant_id=tenant_id,
        name="银泰百货华东区",
        short_name=DEMO_EXTENDED_MARKER,
        industry="commercial",
        confidentiality_level="normal",
        address="杭州市拱墅区延安路 530 号",
        remark="演示客户 · 商业综合体年度营销",
        created_by=admin.id,
    )
    c_mall = BizClient(
        tenant_id=tenant_id,
        name="星汇商业运营管理公司",
        short_name="demo-mall-ops",
        industry="commercial",
        confidentiality_level="normal",
        address="南京市建邺区",
        remark="演示客户 · 开业活动与导视",
        created_by=admin.id,
    )
    session.add_all([c_retail, c_mall])
    await session.flush()

    session.add_all([
        BizClientContact(
            tenant_id=tenant_id, client_id=c_retail.id, name="赵敏", title="市场部经理",
            phone="13800005001", email="zhao@retail-demo.local", is_primary=True,
        ),
        BizClientContact(
            tenant_id=tenant_id, client_id=c_mall.id, name="孙磊", title="运营总监",
            phone="13800006001", is_primary=True,
        ),
    ])

    session.add_all([
        BizOpportunity(
            tenant_id=tenant_id, client_id=c_retail.id,
            name="2026 春季美陈焕新",
            code="OPP-DEMO-004", stage="prospecting",
            expected_value=85_000, probability=30,
            expected_close_date=today + timedelta(days=60),
            owner_id=admin.id, created_by=admin.id,
            description="商场中庭与主入口季节性美陈。",
        ),
        BizOpportunity(
            tenant_id=tenant_id, client_id=c_mall.id,
            name="星汇广场开业盛典",
            code="OPP-DEMO-005", stage="qualification",
            expected_value=520_000, probability=45,
            expected_close_date=today + timedelta(days=35),
            owner_id=admin.id, created_by=admin.id,
        ),
        BizOpportunity(
            tenant_id=tenant_id, client_id=c_hailan.id,
            name="文旅 IP 联名快闪（未中标）",
            code="OPP-DEMO-006", stage="lost",
            expected_value=200_000, probability=0,
            expected_close_date=today - timedelta(days=10),
            owner_id=admin.id, created_by=admin.id,
            description="竞品低价中标，留档复盘。",
        ),
    ])
    await session.flush()

    p_brand = BizProject(
        tenant_id=tenant_id, client_id=c_retail.id,
        code="PJ-DEMO-004", name="银泰华东 VI 年度更新",
        status="delivered", total_budget=180_000,
        description="已完成交付并结项演示。",
        owner_id=admin.id,
        start_date=today - timedelta(days=120),
        end_date=today - timedelta(days=15),
        created_by=admin.id,
    )
    p_draft = BizProject(
        tenant_id=tenant_id, client_id=c_park.id,
        code="PJ-DEMO-005", name="园区导视系统升级（筹备）",
        status="draft", total_budget=95_000,
        description="草稿项目，待立项评审。",
        owner_id=admin.id, created_by=admin.id,
    )
    p_hold = BizProject(
        tenant_id=tenant_id, client_id=c_mall.id,
        code="PJ-DEMO-006", name="星汇开业活动执行",
        status="on_hold", total_budget=520_000,
        description="客户暂缓，等待场地确认。",
        owner_id=admin.id, created_by=admin.id,
    )
    session.add_all([p_brand, p_draft, p_hold])
    await session.flush()

    bi_stage, bi_idx = _stage("brand_identity", 2)
    sg_stage, sg_idx = _stage("signage", 1)
    ev_stage2, ev_idx2 = _stage("event", 0)

    wp_brand = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_brand.id,
        service_line="brand_identity", name="VI 升级包",
        stage=bi_stage, stage_index=bi_idx,
        status="done", budget=160_000, actual_cost=152_000,
        owner_id=admin.id,
    )
    wp_sign_draft = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_draft.id,
        service_line="signage", name="园区导视规划",
        stage=sg_stage, stage_index=sg_idx,
        status="pending", budget=95_000,
        owner_id=admin.id,
    )
    wp_event_hold = BizWorkPackage(
        tenant_id=tenant_id, project_id=p_hold.id,
        service_line="event", name="开业活动方案",
        stage=ev_stage2, stage_index=ev_idx2,
        status="pending", budget=300_000,
        owner_id=admin.id,
    )
    session.add_all([wp_brand, wp_sign_draft, wp_event_hold])
    await session.flush()

    session.add(BizProjectMember(
        tenant_id=tenant_id, project_id=p_brand.id,
        user_id=admin.id, role_in_project="owner",
    ))

    session.add_all([
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_brand.id, work_package_id=wp_brand.id,
            name="VI 手册终稿", type="document", status="accepted", version="v3.0",
            submitted_at=f"{(today - timedelta(days=20)).isoformat()}T10:00:00Z",
            accepted_at=f"{(today - timedelta(days=18)).isoformat()}T15:00:00Z",
            created_by=admin.id,
        ),
        BizDeliverable(
            tenant_id=tenant_id, project_id=p_brand.id,
            name="辅助图形方案", type="design", status="rejected", version="v1.1",
            submitted_at=f"{(today - timedelta(days=25)).isoformat()}T10:00:00Z",
            created_by=admin.id,
        ),
    ])

    ctr_brand = BizContract(
        tenant_id=tenant_id, project_id=p_brand.id, client_id=c_retail.id,
        name="银泰 VI 更新服务合同", contract_no="CTR-DEMO-003",
        type="service", status="completed", total_amount=180_000,
        signed_date=today - timedelta(days=115),
        start_date=today - timedelta(days=115), end_date=today - timedelta(days=20),
        created_by=admin.id,
    )
    ctr_nda = BizContract(
        tenant_id=tenant_id, project_id=p_hold.id, client_id=c_mall.id,
        name="星汇开业保密协议", contract_no="CTR-DEMO-004",
        type="nda", status="pending_sign", total_amount=0,
        created_by=admin.id,
    )
    session.add_all([ctr_brand, ctr_nda])
    await session.flush()

    session.add(BizPayment(
        tenant_id=tenant_id, contract_id=ctr_brand.id, project_id=p_brand.id,
        name="尾款 30%", direction="in", amount=54_000, status="paid",
        planned_date=today - timedelta(days=20), paid_date=today - timedelta(days=19),
        created_by=admin.id,
    ))

    s_design = BizSupplier(
        tenant_id=tenant_id, name="留白设计顾问", short_name="留白设计",
        category="design", status="active",
        contact_name="顾设计师", contact_phone="13900007001",
        created_by=admin.id,
    )
    s_event = BizSupplier(
        tenant_id=tenant_id, name="拾光活动执行", short_name="拾光活动",
        category="event", status="active",
        contact_name="何总", contact_phone="13900008001",
        created_by=admin.id,
    )
    s_bad = BizSupplier(
        tenant_id=tenant_id, name="某失信搭建公司", short_name="失信搭建",
        category="construction", status="blacklisted",
        contact_name="—", remark="演示黑名单供应商",
        created_by=admin.id,
    )
    session.add_all([s_design, s_event, s_bad])
    await session.flush()

    session.add(BizProjectSupplier(
        tenant_id=tenant_id, project_id=p_brand.id, supplier_id=s_design.id,
        work_package_id=wp_brand.id, role_description="VI 设计顾问",
        contracted_amount=45_000, status="completed",
    ))

    # 租户模板市场「我的发布」：草稿 / 已上架 / 已驳回
    session.add_all([
        BizServiceLineTemplatePack(
            tenant_id=tenant_id,
            category="exhibition",
            service_line="exhibition",
            name="海岚展陈精简版（租户分享）",
            description="基于海岚项目经验压缩的展陈阶段，供团队内部复用。",
            stages=["叙事大纲", "空间效果图", "落地清单"],
            ai_config=DEFAULT_SERVICE_LINE_AI.get("exhibition", {}),
            publisher_name="默认租户",
            publisher_type="tenant",
            tags=["tourism", "government"],
            status=TemplatePackStatus.PUBLISHED.value,
            is_active=True,
            install_count=2,
        ),
        BizServiceLineTemplatePack(
            tenant_id=tenant_id,
            category="event",
            service_line="event",
            name="园区开放日方案（草稿）",
            description="待完善的活动执行 checklist。",
            stages=["方案", "执行", "复盘"],
            ai_config=DEFAULT_SERVICE_LINE_AI.get("event", {}),
            publisher_name="默认租户",
            publisher_type="tenant",
            tags=["park"],
            status=TemplatePackStatus.DRAFT.value,
            is_active=True,
        ),
        BizServiceLineTemplatePack(
            tenant_id=tenant_id,
            category="brand",
            service_line="brand_identity",
            name="快启品牌包（驳回示例）",
            description="阶段过少，需补充实施与交付环节。",
            stages=["定位", "VI"],
            ai_config=DEFAULT_SERVICE_LINE_AI.get("brand_identity", {}),
            publisher_name="默认租户",
            publisher_type="tenant",
            tags=["enterprise"],
            status=TemplatePackStatus.REJECTED.value,
            is_active=True,
            review_note="请补充「手册交付」阶段及 AI 对话提示后再提交。",
        ),
    ])

    await session.flush()
    return True
