"use client";

import Link from "next/link";
import { ProjectsTable } from "@/features/projects/components/ProjectsTable";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";

export function ProjectsPageView({ vm }: { vm: ProjectsPageVm }) {
  const { ready, confirmDialog } = vm;

  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">项目</h1>
          <p className="mt-1 text-sm text-ink-muted">管理品牌、影视、展览、活动等全流程项目交付</p>
        </div>
        <Link href="/business/projects/new" className="btn-primary text-sm">新建项目</Link>
      </div>
      <ProjectsTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
