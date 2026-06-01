"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { ProjectsTable } from "@/features/projects/components/ProjectsTable";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";

export function ProjectsPageView({ vm }: { vm: ProjectsPageVm }) {
  const { ready, confirmDialog } = vm;

  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        subtitle="商机赢单后立项；工作包、交付物、成员与结项均在此管理"
        actions={<Link href="/business/projects/new" className="btn-primary text-sm">新建项目</Link>}
      />
      <ProjectsTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
