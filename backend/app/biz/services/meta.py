from app.biz.schemas.meta import BizMetaOut, EnumItem

# 八条服务线（与设计文档一致）
SERVICE_LINES = [
    EnumItem("brand_identity", "品牌形象"),
    EnumItem("video_production", "影视拍摄"),
    EnumItem("exhibition", "展览展示"),
    EnumItem("event", "活动策划"),
    EnumItem("training", "会务培训"),
    EnumItem("signage", "标识设计"),
    EnumItem("cultural_product", "文创产品"),
    EnumItem("print", "宣传品设计印刷"),
]

PROJECT_STATUSES = [
    EnumItem("draft", "草稿"),
    EnumItem("active", "进行中"),
    EnumItem("on_hold", "暂停"),
    EnumItem("delivered", "已交付"),
    EnumItem("closed", "已结项"),
    EnumItem("cancelled", "已取消"),
]

WORK_PACKAGE_STATUSES = [
    EnumItem("pending", "待开始"),
    EnumItem("in_progress", "进行中"),
    EnumItem("review", "审核中"),
    EnumItem("done", "已完成"),
    EnumItem("cancelled", "已取消"),
]

INDUSTRIES = [
    EnumItem("government", "政府机关"),
    EnumItem("enterprise", "企业"),
    EnumItem("park", "园区"),
    EnumItem("commercial", "商业综合体"),
    EnumItem("tourism", "文旅"),
    EnumItem("other", "其他"),
]

CONFIDENTIALITY_LEVELS = [
    EnumItem("normal", "普通"),
    EnumItem("internal", "内部"),
    EnumItem("restricted", "涉密"),
]

OPPORTUNITY_STAGES = [
    EnumItem("prospecting", "线索"),
    EnumItem("qualification", "资质确认"),
    EnumItem("proposal", "方案报价"),
    EnumItem("negotiation", "谈判"),
    EnumItem("won", "赢单"),
    EnumItem("lost", "丢单"),
]

QUOTE_STATUSES = [
    EnumItem("draft", "草稿"),
    EnumItem("sent", "已发送"),
    EnumItem("accepted", "已接受"),
    EnumItem("rejected", "已拒绝"),
    EnumItem("expired", "已过期"),
]

SUPPLIER_CATEGORIES = [
    EnumItem("print", "印刷"),
    EnumItem("video", "影视拍摄"),
    EnumItem("construction", "搭建施工"),
    EnumItem("event", "活动执行"),
    EnumItem("design", "设计外包"),
    EnumItem("logistics", "物流运输"),
    EnumItem("other", "其他"),
]

SUPPLIER_STATUSES = [
    EnumItem("active", "合作中"),
    EnumItem("inactive", "暂停合作"),
    EnumItem("blacklisted", "黑名单"),
]

PROJECT_SUPPLIER_STATUSES = [
    EnumItem("active", "进行中"),
    EnumItem("completed", "已完成"),
    EnumItem("cancelled", "已取消"),
]


class BizMetaService:
    @staticmethod
    def get_meta() -> BizMetaOut:
        from app.biz.services.template_pack_meta import TEMPLATE_PACK_CATEGORIES

        return BizMetaOut(
            service_lines=SERVICE_LINES,
            project_statuses=PROJECT_STATUSES,
            work_package_statuses=WORK_PACKAGE_STATUSES,
            industries=INDUSTRIES,
            confidentiality_levels=CONFIDENTIALITY_LEVELS,
            opportunity_stages=OPPORTUNITY_STAGES,
            quote_statuses=QUOTE_STATUSES,
            supplier_categories=SUPPLIER_CATEGORIES,
            supplier_statuses=SUPPLIER_STATUSES,
            project_supplier_statuses=PROJECT_SUPPLIER_STATUSES,
            template_pack_categories=TEMPLATE_PACK_CATEGORIES,
        )
