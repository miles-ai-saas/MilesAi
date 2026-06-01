"use client";

import Link from "next/link";
import { AI_CARDS, PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import { ProjectDeliverablesTab } from "@/features/projects/components/ProjectDeliverablesTab";
import { ProjectMembersTab } from "@/features/projects/components/ProjectMembersTab";
import { ProjectWorkPackagesTab } from "@/features/projects/components/ProjectWorkPackagesTab";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";
import type { BizProject } from "@/lib/types";

const TABS = [
  { id: "info" as const, label: "基本信息" },
  { id: "workpackages" as const, label: "工作包" },
  { id: "deliverables" as const, label: "交付物" },
  { id: "members" as const, label: "成员" },
  { id: "ai" as const, label: "AI 服务" },
];

export function ProjectDetailView({ vm }: { vm: ProjectDetailPageVm }) {
  const { router, project, loading, error, tab, deliverables, members, handleTabChange } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !project) return <p className="text-sm text-red-600">{error || "项目不存在"}</p>;

  const tabLabel = (id: typeof TABS[number]["id"]) => {
    if (id === "workpackages") return `工作包 (${project.work_packages?.length ?? 0})`;
    if (id === "deliverables") return `交付物 (${deliverables.length})`;
    if (id === "members") return `成员 (${members.length})`;
    return TABS.find((t) => t.id === id)?.label ?? id;
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
          {PROJECT_STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>

      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={`shrink-0 px-4 py-2 text-sm font-medium transition ${tab === t.id ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`} onClick={() => handleTabChange(t.id)}>
            {tabLabel(t.id)}
          </button>
        ))}
      </div>

      {tab === "info" && <ProjectInfoTab project={project} />}
      {tab === "workpackages" && <ProjectWorkPackagesTab vm={vm} />}
      {tab === "deliverables" && <ProjectDeliverablesTab vm={vm} />}
      {tab === "members" && <ProjectMembersTab vm={vm} />}
      {tab === "ai" && <ProjectAiTab />}
    </div>
  );
}

function ProjectInfoTab({ project }: { project: BizProject }) {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <InfoCard label="描述" value={project.description || "—"} />
      <InfoCard label="总预算" value={project.total_budget ? `¥${project.total_budget.toLocaleString()}` : "—"} />
      <InfoCard label="工作包数" value={`${project.work_packages?.length ?? 0}`} />
      <InfoCard label="项目编号" value={project.code || "—"} />
    </div>
  );
}

function ProjectAiTab() {
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
