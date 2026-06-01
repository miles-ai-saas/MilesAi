import { get, getPage, post, patch, put, http, unwrap } from "./client";
import { buildPageQuery } from "../pagination";
import type { BizArchiveCaseResult, BizClient, BizClientContact, BizClosePreview, BizCloseWizardResult, BizContract, BizDeliverable, BizMilestone, BizOpportunity, BizPayment, BizProject, BizProjectActivityItem, BizProjectAiContext, BizProjectCostSummary, BizProjectMember, BizProjectSupplier, BizQuote, BizSearchResult, BizServiceLineAiConfig, BizServiceLineTemplate, BizSupplier, BizSupplierContact, BizWorkPackage, BizWorkPackageKanban, DashboardSummary, DueMilestoneItem, FinancialSummary } from "../types";

export const bizApi = {
  // ── 业务仪表盘 ──

  getDashboardSummary: () => get<DashboardSummary>("/biz/dashboard/summary"),

  // ── 客户管理 ──

  listClients: (page = 1, size = 20, search?: string) => {
    let q = buildPageQuery(page, size);
    if (search) q += `&search=${encodeURIComponent(search)}`;
    return getPage<BizClient>(`/biz/clients?${q}`);
  },

  getClient: (id: string) => get<BizClient>(`/biz/clients/${id}`),
  createClient: (p: { name: string; short_name?: string; industry?: string; confidentiality_level?: string; address?: string; remark?: string }) => post<BizClient>("/biz/clients", p),
  updateClient: (id: string, p: { name?: string; short_name?: string; industry?: string; confidentiality_level?: string; address?: string; remark?: string }) => patch<BizClient>(`/biz/clients/${id}`, p),
  deleteClient: (id: string) => http.delete(`/biz/clients/${id}`).then(() => undefined),

  listContacts: (clientId: string) => get<BizClientContact[]>(`/biz/clients/${clientId}/contacts`),
  createContact: (clientId: string, p: { name: string; title?: string; phone?: string; email?: string; is_primary?: boolean }) => post<BizClientContact>(`/biz/clients/${clientId}/contacts`, p),
  updateContact: (clientId: string, contactId: string, p: { name?: string; title?: string; phone?: string; email?: string; is_primary?: boolean }) => patch<BizClientContact>(`/biz/clients/${clientId}/contacts/${contactId}`, p),
  deleteContact: (clientId: string, contactId: string) => http.delete(`/biz/clients/${clientId}/contacts/${contactId}`).then(() => undefined),

  // ── 项目管理 ──

  listProjects: (page = 1, size = 20, clientId?: string, status?: string) => {
    let q = buildPageQuery(page, size);
    if (clientId) q += `&client_id=${clientId}`;
    if (status) q += `&status=${status}`;
    return getPage<BizProject>(`/biz/projects?${q}`);
  },

  getProject: (id: string) => get<BizProject>(`/biz/projects/${id}`),
  createProject: (p: { client_id: string; name: string; code?: string; owner_id?: string; description?: string; total_budget?: number; work_packages?: { service_line: string; name: string }[] }) => post<BizProject>("/biz/projects", p),
  updateProject: (id: string, p: { name?: string; code?: string; status?: string; owner_id?: string; description?: string; total_budget?: number }) => patch<BizProject>(`/biz/projects/${id}`, p),
  deleteProject: (id: string) => http.delete(`/biz/projects/${id}`).then(() => undefined),

  listWorkPackages: (projectId: string) => get<BizWorkPackage[]>(`/biz/projects/${projectId}/work-packages`),
  listWorkPackagesKanban: (projectId?: string, serviceLine?: string, status?: string) => {
    let q = "/biz/work-packages?limit=200";
    if (projectId) q += `&project_id=${projectId}`;
    if (serviceLine) q += `&service_line=${serviceLine}`;
    if (status) q += `&status=${status}`;
    return get<BizWorkPackageKanban[]>(q);
  },
  createWorkPackage: (projectId: string, p: { service_line: string; name: string; stage?: string; stage_index?: number; status?: string; owner_id?: string; budget?: number; planned_start?: string; planned_end?: string }) =>
    post<BizWorkPackage>(`/biz/projects/${projectId}/work-packages`, p),
  updateWorkPackage: (projectId: string, wpId: string, p: { name?: string; stage?: string; status?: string; owner_id?: string; budget?: number; actual_cost?: number }) => patch<BizWorkPackage>(`/biz/projects/${projectId}/work-packages/${wpId}`, p),
  deleteWorkPackage: (projectId: string, wpId: string) => http.delete(`/biz/projects/${projectId}/work-packages/${wpId}`).then(() => undefined),
  advanceWorkPackageStage: (wpId: string) => post<BizWorkPackage>(`/biz/work-packages/${wpId}/advance-stage`, {}),
  rollbackWorkPackageStage: (wpId: string) => post<BizWorkPackage>(`/biz/work-packages/${wpId}/rollback-stage`, {}),

  getProjectCostSummary: (projectId: string) => get<BizProjectCostSummary>(`/biz/projects/${projectId}/cost-summary`),
  getClosePreview: (projectId: string) => get<BizClosePreview>(`/biz/projects/${projectId}/close-preview`),
  executeCloseWizard: (projectId: string, p: { kb_id?: string; deliverable_ids?: string[]; run_parse?: boolean; skip_archive?: boolean; confirm_desensitized?: boolean }) =>
    post<BizCloseWizardResult>(`/biz/projects/${projectId}/close-wizard`, p),
  closeProject: (projectId: string) => post<{ id: string; status: string }>(`/biz/projects/${projectId}/close`, {}),
  archiveProjectCase: (projectId: string, p: { kb_id: string; run_parse?: boolean }) =>
    post<BizArchiveCaseResult>(`/biz/projects/${projectId}/archive-case`, p),

  listMilestones: (projectId: string, wpId: string) =>
    get<BizMilestone[]>(`/biz/projects/${projectId}/work-packages/${wpId}/milestones`),
  listDueMilestones: (days = 7) => get<DueMilestoneItem[]>(`/biz/milestones/due?days=${days}`),
  createMilestone: (projectId: string, wpId: string, p: { title: string; due_date?: string; sort_order?: number }) =>
    post<BizMilestone>(`/biz/projects/${projectId}/work-packages/${wpId}/milestones`, p),
  updateMilestone: (projectId: string, wpId: string, milestoneId: string, p: { title?: string; due_date?: string; completed_at?: string | null; sort_order?: number }) =>
    patch<BizMilestone>(`/biz/projects/${projectId}/work-packages/${wpId}/milestones/${milestoneId}`, p),
  deleteMilestone: (projectId: string, wpId: string, milestoneId: string) =>
    http.delete(`/biz/projects/${projectId}/work-packages/${wpId}/milestones/${milestoneId}`).then(() => undefined),

  listProjectMembers: (projectId: string) => get<BizProjectMember[]>(`/biz/projects/${projectId}/members`),
  addProjectMember: (projectId: string, p: { user_id: string; role_in_project?: string }) =>
    post<BizProjectMember>(`/biz/projects/${projectId}/members`, p),
  removeProjectMember: (projectId: string, userId: string) =>
    http.delete(`/biz/projects/${projectId}/members/${userId}`).then(() => undefined),

  // ── 交付物管理 ──

  listDeliverables: (projectId: string) => get<BizDeliverable[]>(`/biz/deliverables?project_id=${projectId}`),
  createDeliverable: (p: { project_id: string; name: string; type?: string; work_package_id?: string; attachment_id?: string; version?: string }) => post<BizDeliverable>("/biz/deliverables", p),
  updateDeliverable: (id: string, p: { name?: string; type?: string; status?: string; work_package_id?: string; attachment_id?: string; media_asset_id?: string; version?: string }) => patch<BizDeliverable>(`/biz/deliverables/${id}`, p),
  submitDeliverable: (id: string) => post<BizDeliverable>(`/biz/deliverables/${id}/submit`, {}),
  acceptDeliverable: (id: string) => post<BizDeliverable>(`/biz/deliverables/${id}/accept`, {}),
  rejectDeliverable: (id: string) => post<BizDeliverable>(`/biz/deliverables/${id}/reject`, {}),
  deleteDeliverable: (id: string) => http.delete(`/biz/deliverables/${id}`).then(() => undefined),

  // ── 商机管理 ──

  listOpportunities: (page = 1, size = 20, clientId?: string, stage?: string) => {
    let q = buildPageQuery(page, size);
    if (clientId) q += `&client_id=${clientId}`;
    if (stage) q += `&stage=${stage}`;
    return getPage<BizOpportunity>(`/biz/opportunities?${q}`);
  },

  listOpportunityPipeline: () => get<BizOpportunity[]>("/biz/opportunities/pipeline"),

  getOpportunity: (id: string) => get<BizOpportunity>(`/biz/opportunities/${id}`),
  createOpportunity: (p: { client_id: string; name: string; code?: string; stage?: string; expected_value?: number; probability?: number; expected_close_date?: string; owner_id?: string; description?: string }) => post<BizOpportunity>("/biz/opportunities", p),
  updateOpportunity: (id: string, p: { name?: string; code?: string; stage?: string; expected_value?: number; probability?: number; expected_close_date?: string; owner_id?: string; description?: string }) => patch<BizOpportunity>(`/biz/opportunities/${id}`, p),
  deleteOpportunity: (id: string) => http.delete(`/biz/opportunities/${id}`).then(() => undefined),
  convertOpportunityToProject: (id: string) =>
    post<{ opportunity: BizOpportunity; project_id: string }>(`/biz/opportunities/${id}/convert-to-project`, {}),

  listQuotes: (opportunityId: string) => get<BizQuote[]>(`/biz/opportunities/${opportunityId}/quotes`),
  createQuote: (opportunityId: string, p: { name: string; amount?: number; status?: string; version?: string; valid_until?: string; remark?: string }) =>
    post<BizQuote>(`/biz/opportunities/${opportunityId}/quotes`, p),
  updateQuote: (opportunityId: string, quoteId: string, p: { name?: string; amount?: number; status?: string; version?: string; valid_until?: string; remark?: string }) =>
    patch<BizQuote>(`/biz/opportunities/${opportunityId}/quotes/${quoteId}`, p),
  deleteQuote: (opportunityId: string, quoteId: string) =>
    http.delete(`/biz/opportunities/${opportunityId}/quotes/${quoteId}`).then(() => undefined),

  // ── 合同管理 ──

  listContracts: (page = 1, size = 20, projectId?: string, status?: string, clientId?: string) => {
    let q = buildPageQuery(page, size);
    if (projectId) q += `&project_id=${projectId}`;
    if (clientId) q += `&client_id=${clientId}`;
    if (status) q += `&status=${status}`;
    return getPage<BizContract>(`/biz/contracts?${q}`);
  },

  getContract: (id: string) => get<BizContract>(`/biz/contracts/${id}`),
  createContract: (p: { project_id: string; client_id: string; name: string; contract_no?: string; type?: string; signed_date?: string; start_date?: string; end_date?: string; total_amount?: number; payment_terms?: string; description?: string }) => post<BizContract>("/biz/contracts", p),
  updateContract: (id: string, p: { name?: string; contract_no?: string; type?: string; status?: string; signed_date?: string; start_date?: string; end_date?: string; total_amount?: number; payment_terms?: string; description?: string }) => patch<BizContract>(`/biz/contracts/${id}`, p),
  deleteContract: (id: string) => http.delete(`/biz/contracts/${id}`).then(() => undefined),

  // ── 收付款管理 ──

  getFinancialSummary: () => get<FinancialSummary>("/biz/payments/financial-summary"),

  listPendingPayments: () => get<BizPayment[]>("/biz/payments/pending"),

  listPayments: (contractId: string) => get<BizPayment[]>(`/biz/payments?contract_id=${contractId}`),

  createPayment: (p: { contract_id: string; project_id: string; name: string; direction?: string; amount?: number; planned_date?: string; method?: string; remark?: string }) =>
    post<BizPayment>("/biz/payments", p),

  updatePayment: (id: string, p: { name?: string; direction?: string; amount?: number; planned_date?: string; paid_date?: string; method?: string; status?: string; remark?: string }) =>
    patch<BizPayment>(`/biz/payments/${id}`, p),

  deletePayment: (id: string) => http.delete(`/biz/payments/${id}`).then(() => undefined),

  // ── 供应商管理 ──

  listSuppliers: (page = 1, size = 20, search?: string, category?: string, status?: string) => {
    let q = buildPageQuery(page, size);
    if (search) q += `&search=${encodeURIComponent(search)}`;
    if (category) q += `&category=${category}`;
    if (status) q += `&status=${status}`;
    return getPage<BizSupplier>(`/biz/suppliers?${q}`);
  },

  getSupplier: (id: string) => get<BizSupplier>(`/biz/suppliers/${id}`),
  createSupplier: (p: { name: string; short_name?: string; category?: string; status?: string; contact_name?: string; contact_phone?: string; contact_email?: string; address?: string; bank_name?: string; bank_account?: string; remark?: string }) =>
    post<BizSupplier>("/biz/suppliers", p),
  updateSupplier: (id: string, p: { name?: string; short_name?: string; category?: string; status?: string; contact_name?: string; contact_phone?: string; contact_email?: string; address?: string; bank_name?: string; bank_account?: string; remark?: string }) =>
    patch<BizSupplier>(`/biz/suppliers/${id}`, p),
  deleteSupplier: (id: string) => http.delete(`/biz/suppliers/${id}`).then(() => undefined),

  listSupplierContacts: (supplierId: string) => get<BizSupplierContact[]>(`/biz/suppliers/${supplierId}/contacts`),
  createSupplierContact: (supplierId: string, p: { name: string; title?: string; phone?: string; email?: string; is_primary?: boolean }) =>
    post<BizSupplierContact>(`/biz/suppliers/${supplierId}/contacts`, p),
  updateSupplierContact: (supplierId: string, contactId: string, p: { name: string; title?: string; phone?: string; email?: string; is_primary?: boolean }) =>
    patch<BizSupplierContact>(`/biz/suppliers/${supplierId}/contacts/${contactId}`, p),
  deleteSupplierContact: (supplierId: string, contactId: string) =>
    http.delete(`/biz/suppliers/${supplierId}/contacts/${contactId}`).then(() => undefined),

  listProjectSuppliers: (projectId: string) => get<BizProjectSupplier[]>(`/biz/projects/${projectId}/suppliers`),
  addProjectSupplier: (projectId: string, p: { supplier_id: string; work_package_id?: string; role_description?: string; contracted_amount?: number; status?: string; remark?: string }) =>
    post<BizProjectSupplier>(`/biz/projects/${projectId}/suppliers`, p),
  updateProjectSupplier: (projectId: string, supplierId: string, p: { work_package_id?: string; role_description?: string; contracted_amount?: number; status?: string; remark?: string }) =>
    patch<BizProjectSupplier>(`/biz/projects/${projectId}/suppliers/${supplierId}`, p),
  removeProjectSupplier: (projectId: string, supplierId: string) =>
    http.delete(`/biz/projects/${projectId}/suppliers/${supplierId}`).then(() => undefined),

  getProjectAiContext: (projectId: string, workPackageId?: string) => {
    let q = `/biz/projects/${projectId}/ai-context`;
    if (workPackageId) q += `?work_package_id=${workPackageId}`;
    return get<BizProjectAiContext>(q);
  },

  // ── 导出 ──

  exportProjectsCsv: (clientId?: string, status?: string) => {
    let q = "/biz/export/projects.csv";
    const params: string[] = [];
    if (clientId) params.push(`client_id=${clientId}`);
    if (status) params.push(`status=${status}`);
    if (params.length) q += `?${params.join("&")}`;
    return q;
  },

  exportOpportunitiesCsv: (clientId?: string, stage?: string) => {
    let q = "/biz/export/opportunities.csv";
    const params: string[] = [];
    if (clientId) params.push(`client_id=${clientId}`);
    if (stage) params.push(`stage=${stage}`);
    if (params.length) q += `?${params.join("&")}`;
    return q;
  },

  exportPaymentsCsv: () => "/biz/export/payments.csv",

  // ── 服务线模板 ──

  listServiceLineTemplates: () => get<BizServiceLineTemplate[]>("/biz/service-line-templates"),
  upsertServiceLineTemplate: (serviceLine: string, p: { stages: string[]; is_active?: boolean; ai_config?: BizServiceLineAiConfig }) =>
    put<BizServiceLineTemplate>(`/biz/service-line-templates/${serviceLine}`, p),
  resetServiceLineTemplate: (serviceLine: string) =>
    http.delete(`/biz/service-line-templates/${serviceLine}`).then((r) => unwrap<BizServiceLineTemplate>(r.data)),

  searchBiz: (q: string, limit = 12) => get<BizSearchResult>(`/biz/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  listProjectActivity: (projectId: string, limit = 30) =>
    get<BizProjectActivityItem[]>(`/biz/projects/${projectId}/activity?limit=${limit}`),
};
