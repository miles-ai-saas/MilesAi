/** 业务中心前端类型定义。
 *
 * 对齐后端 app/biz/schemas/*.py 的 Pydantic schemas，
 * 字段命名保持 Python snake_case 以匹配 JSON 反序列化。
 */

/** 客户联系人 */
export interface BizClientContact {
  id: string;
  client_id: string;
  name: string;
  title?: string;       // 职位/头衔
  phone?: string;
  email?: string;
  is_primary: boolean;  // 是否主要联系人
}

/** 客户（品牌方/下单方），业务实体的核心锚点 */
export interface BizClient {
  id: string;
  name: string;
  short_name?: string;
  industry?: string;
  confidentiality_level: string;  // normal | internal | restricted
  address?: string;
  remark?: string;
  project_count: number;          // 关联的在制项目数（聚合字段，非持久化）
  contacts: BizClientContact[];
}

/** 工作包——项目按服务线拆分的执行单元 */
export interface BizWorkPackage {
  id: string;
  project_id: string;
  service_line: string;   // 服务线类型 brand_identity | video_production | ...
  name: string;
  stage?: string;         // 当前阶段名称（来自服务线模板）
  stage_index: number;    // 阶段序号，用于排序
  status: string;         // pending | in_progress | review | done | cancelled
  owner_id?: string;
  budget?: number;        // 预算金额
  actual_cost?: number;   // 实际成本
  planned_start?: string;
  planned_end?: string;
}

/** 项目——交付的核心组织单元 */
export interface BizProject {
  id: string;
  client_id: string;
  name: string;
  status: string;         // draft | active | on_hold | delivered | ...
  code?: string;          // 项目编号（如 PROJ-2024-001）
  owner_id?: string;      // 项目负责人
  description?: string;
  total_budget?: number;
  work_packages: BizWorkPackage[];
}

/** 项目成员 */
export interface BizProjectMember {
  project_id: string;
  user_id: string;
  role_in_project: string;
  username?: string;
}

/** 交付物——项目产出的文档/设计稿/视频等 */
export interface BizDeliverable {
  id: string;
  project_id: string;
  name: string;
  type: string;           // document | image | video | design | other
  status: string;         // draft | submitted | accepted | rejected
  work_package_id?: string;
  attachment_id?: string;    // 关联附件表 ID
  media_asset_id?: string;   // 关联媒体资产 ID
  version?: string;
  submitted_at?: string;     // 提交时间
  accepted_at?: string;      // 验收时间
}

/** 仪表盘总览统计 */
export interface DashboardSummary {
  total_clients: number;
  active_projects: number;          // 在制项目数（草稿+进行中+暂停）
  pending_deliverables: number;     // 已提交待验收交付物
  work_packages_in_progress: number;
  recent_projects: {
    id: string;
    name: string;
    status: string;
    client_name: string;            // 关联客户名称
  }[];
}

/** 商机——销售漏斗管理 */
export interface BizOpportunity {
  id: string;
  client_id: string;
  name: string;
  stage: string;         // prospecting→qualification→proposal→negotiation→won/lost
  code?: string;
  expected_value?: number;  // 预估成交金额
  probability?: number;     // 赢单概率 0-100
  expected_close_date?: string;
  owner_id?: string;
  description?: string;
  converted_to_project_id?: string;  // 赢单后转为项目的 ID
}

/** 合同——项目签约管理 */
export interface BizContract {
  id: string;
  project_id: string;
  client_id: string;
  name: string;
  status: string;    // draft | pending_sign | signed | active | completed | terminated
  type: string;      // service | nda | framework | other
  contract_no?: string;
  signed_date?: string;
  start_date?: string;
  end_date?: string;
  total_amount?: number;
  payment_terms?: string;  // 付款条款描述（如 30%预付+70%验收后）
  description?: string;
}

/** 收付款记录——合同项下款项管理 */
export interface BizPayment {
  id: string;
  contract_id: string;
  project_id: string;
  name: string;
  direction: string;  // in=收款 out=付款
  amount: number;
  status: string;     // pending | processing | paid | cancelled
  planned_date?: string;   // 计划收付日期
  paid_date?: string;      // 实际收付日期
  method?: string;          // 银行转账/支票/现金
  remark?: string;
}

/** 财务概览统计 */
export interface FinancialSummary {
  total_income: number;       // 收付款总额
  total_paid: number;         // 已结清金额
  total_pending_in: number;   // 待收款
  total_pending_out: number;  // 待付款
  contract_count: number;     // 合同总数
}

/** 工作包里程碑 */
export interface BizMilestone {
  id: string;
  project_id: string;
  work_package_id: string;
  title: string;
  due_date?: string;
  completed_at?: string;
  sort_order: number;
}

/** 商机报价 */
export interface BizQuote {
  id: string;
  opportunity_id: string;
  client_id: string;
  name: string;
  amount?: number;
  status: string;
  version?: string;
  valid_until?: string;
  remark?: string;
  created_by?: string;
}

/** 项目成本汇总 */
export interface BizProjectCostSummary {
  project_id: string;
  total_budget?: number;
  work_package_budget_total?: number;
  work_package_actual_total?: number;
  budget_variance?: number;
  work_packages: {
    id: string;
    name: string;
    service_line: string;
    budget?: number;
    actual_cost?: number;
    variance?: number;
  }[];
}

/** 案例入库结果 */
export interface BizArchiveCaseResult {
  project_id: string;
  kb_id: string;
  archived_count: number;
  document_ids: string[];
}
