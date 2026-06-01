/** 项目详情页 —— 四个标签页：
 * - 基本信息：项目属性和状态
 * - 工作包：按服务线拆分的执行单元，支持状态更新
 * - 交付物：项目产出的文档/设计稿/视频，支持增删改查
 * - AI 服务：快捷跳转到 AI 工作台（对话、知识库、工作流）
 */

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizDeliverable, BizProject, BizWorkPackage } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = { draft: "草稿", active: "进行中", on_hold: "暂停", delivered: "已交付", closed: "已结项", cancelled: "已取消" };
const LINE_LABELS: Record<string, string> = { brand_identity: "品牌形象", video_production: "影视拍摄", exhibition: "展览展示", event: "活动策划", training: "会务培训", signage: "标识设计", cultural_product: "文创产品", print: "宣传品设计印刷" };
const WP_STATUS_LABELS: Record<string, string> = { pending: "待开始", in_progress: "进行中", review: "审核中", done: "已完成", cancelled: "已取消" };
const DELIV_STATUS_LABELS: Record<string, string> = { draft: "草稿", submitted: "已提交", accepted: "已验收", rejected: "已驳回" };
const DELIV_TYPE_LABELS: Record<string, string> = { document: "文档", image: "图片", video: "视频", design: "设计稿", other: "其他" };

const AI_CARDS = [
  { label: "AI 对话", desc: "在智能体中生成文案、脚本、设计说明", href: "/workbench/agents/chat", icon: "💬" },
  { label: "知识库管理", desc: "管理品牌手册、参考资料库", href: "/workbench/knowledge-base", icon: "📚" },
  { label: "工作流编排", desc: "编排审批、创作流水线", href: "/workbench/flows", icon: "🔄" },
];

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<BizProject | null>(null);
  const [deliverables, setDeliverables] = useState<BizDeliverable[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"info" | "workpackages" | "deliverables" | "ai">("info");

  useEffect(() => {
    api.getProject(id).then(setProject).catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [id]);

  const loadDeliverables = () => api.listDeliverables(id).then(setDeliverables);

  const refreshProject = async () => {
    const updated = await api.getProject(id);
    setProject(updated);
  };

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !project) return <p className="text-sm text-red-600">{error || "项目不存在"}</p>;

  const updateWpStatus = async (wp: BizWorkPackage, nextStatus: string) => {
    await api.updateWorkPackage(id, wp.id, { status: nextStatus });
    await refreshProject();
  };

  const handleTabChange = (t: "info" | "workpackages" | "deliverables" | "ai") => {
    setTab(t);
    if (t === "deliverables") loadDeliverables();
  };

  return (
    <div>
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回项目列表</button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{project.name}</h1>
          {project.code && <p className="text-sm text-ink-muted">{project.code}</p>}
        </div>
        <span className={`rounded px-2 py-0.5 text-xs ${project.status === "active" ? "bg-brand-light text-brand" : project.status === "delivered" ? "bg-green-50 text-green-700" : project.status === "cancelled" ? "bg-red-50 text-red-600" : "bg-surface-muted text-ink-muted"}`}>
          {STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>

      <div className="mt-6 flex gap-1 border-b border-line">
        {(["info", "workpackages", "deliverables", "ai"] as const).map((t) => (
          <button key={t} type="button" className={`px-4 py-2 text-sm font-medium transition ${tab === t ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`} onClick={() => handleTabChange(t)}>
            {t === "info" ? "基本信息" : t === "workpackages" ? `工作包 (${project.work_packages?.length ?? 0})` : t === "deliverables" ? `交付物 (${deliverables.length})` : "AI 服务"}
          </button>
        ))}
      </div>

      {tab === "info" && <InfoTab project={project} />}
      {tab === "workpackages" && <WorkPackagesTab project={project} updateWpStatus={updateWpStatus} />}
      {tab === "deliverables" && <DeliverablesTab projectId={id} deliverables={deliverables} onRefresh={loadDeliverables} />}
      {tab === "ai" && <AiTab />}
    </div>
  );
}

function InfoTab({ project }: { project: BizProject }) {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <InfoCard label="描述" value={project.description || "—"} />
      <InfoCard label="总预算" value={project.total_budget ? `¥${project.total_budget.toLocaleString()}` : "—"} />
      <InfoCard label="工作包数" value={`${project.work_packages?.length ?? 0}`} />
      <InfoCard label="项目编号" value={project.code || "—"} />
    </div>
  );
}

function WorkPackagesTab({ project, updateWpStatus }: { project: BizProject; updateWpStatus: (wp: BizWorkPackage, nextStatus: string) => Promise<void> }) {
  return (
    <div className="mt-4 space-y-3">
      {(project.work_packages ?? []).length === 0 && <p className="text-sm text-ink-faint">暂无工作包</p>}
      {project.work_packages?.map((wp) => (
        <div key={wp.id} className="card p-4">
          <div className="flex items-start justify-between">
            <div>
              <span className="font-medium text-ink">{wp.name}</span>
              <span className="ml-2 rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">{LINE_LABELS[wp.service_line] ?? wp.service_line}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded px-2 py-0.5 text-xs ${wp.status === "in_progress" ? "bg-brand-light text-brand" : wp.status === "done" ? "bg-green-50 text-green-700" : "bg-surface-muted text-ink-muted"}`}>
                {WP_STATUS_LABELS[wp.status] ?? wp.status}
              </span>
              {wp.status === "pending" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "in_progress")}>开始</button>}
              {wp.status === "in_progress" && (<><button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "review")}>送审</button><button type="button" className="text-xs text-ink-muted hover:underline" onClick={() => updateWpStatus(wp, "done")}>完成</button></>)}
              {wp.status === "review" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "done")}>通过</button>}
            </div>
          </div>
          {wp.stage && <p className="mt-1 text-xs text-ink-faint">阶段：{wp.stage}</p>}
          <div className="mt-2 flex gap-4 text-xs text-ink-muted">
            {wp.budget != null && <span>预算 ¥{wp.budget.toLocaleString()}</span>}
            {wp.actual_cost != null && <span>实际 ¥{wp.actual_cost.toLocaleString()}</span>}
            {wp.planned_start && <span>{wp.planned_start} ~ {wp.planned_end || "—"}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function DeliverablesTab({ projectId, deliverables, onRefresh }: { projectId: string; deliverables: BizDeliverable[]; onRefresh: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("document");
  const [version, setVersion] = useState("");
  const [saving, setSaving] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.createDeliverable({ project_id: projectId, name: name.trim(), type, version: version.trim() || undefined });
      setName(""); setType("document"); setVersion("");
      onRefresh();
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => { await api.deleteDeliverable(id); onRefresh(); };

  return (
    <div className="mt-4 space-y-4">
      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="flex-1"><span className="text-xs text-ink-muted">名称</span><input className="input-field mt-1 w-full text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="交付物名称" required /></label>
        <label><span className="text-xs text-ink-muted">类型</span><select className="input-field mt-1 text-sm" value={type} onChange={(e) => setType(e.target.value)}>{Object.entries(DELIV_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label><span className="text-xs text-ink-muted">版本</span><input className="input-field mt-1 w-24 text-sm" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v1.0" /></label>
        <button type="submit" disabled={saving || !name.trim()} className="btn-primary text-sm">{saving ? "添加中…" : "添加"}</button>
      </form>
      {deliverables.length === 0 && <p className="text-sm text-ink-faint">暂无交付物</p>}
      {deliverables.map((d) => (
        <div key={d.id} className="card flex items-center justify-between p-4">
          <div><p className="font-medium text-ink">{d.name}{d.version ? <span className="ml-2 text-xs text-ink-faint">{d.version}</span> : null}</p><p className="text-xs text-ink-muted">{DELIV_TYPE_LABELS[d.type] ?? d.type} · {DELIV_STATUS_LABELS[d.status] ?? d.status}</p></div>
          <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => handleDelete(d.id)}>删除</button>
        </div>
      ))}
    </div>
  );
}

function AiTab() {
  return (
    <div className="mt-4 space-y-3">
      <p className="text-sm text-ink-muted">从业务项目深度链接 AI 工作台，进行策划分析、文案创作、设计生成</p>
      {AI_CARDS.map((card) => (
        <Link key={card.href} href={card.href} className="card flex items-center gap-4 p-4 transition hover:shadow-md" target="_blank">
          <span className="text-2xl">{card.icon}</span>
          <div>
            <p className="font-medium text-ink">{card.label}</p>
            <p className="text-xs text-ink-muted">{card.desc}</p>
          </div>
          <span className="ml-auto text-xs text-brand">前往 →</span>
        </Link>
      ))}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return <div className="card p-4"><p className="text-xs text-ink-faint">{label}</p><p className="mt-1 text-sm text-ink">{value}</p></div>;
}
