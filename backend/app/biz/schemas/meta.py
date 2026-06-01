from dataclasses import dataclass, field


@dataclass
class EnumItem:
    key: str
    label: str


@dataclass
class BizMetaOut:
    service_lines: list[EnumItem] = field(default_factory=list)
    project_statuses: list[EnumItem] = field(default_factory=list)
    work_package_statuses: list[EnumItem] = field(default_factory=list)
    industries: list[EnumItem] = field(default_factory=list)
    confidentiality_levels: list[EnumItem] = field(default_factory=list)
    opportunity_stages: list[EnumItem] = field(default_factory=list)
    quote_statuses: list[EnumItem] = field(default_factory=list)
    supplier_categories: list[EnumItem] = field(default_factory=list)
    supplier_statuses: list[EnumItem] = field(default_factory=list)
    project_supplier_statuses: list[EnumItem] = field(default_factory=list)
    template_pack_categories: list[EnumItem] = field(default_factory=list)
