"use client";

import { Suspense } from "react";
import { ProjectsPageView, useProjectsPage } from "@/features/projects";

function ProjectsListPageInner() {
  const vm = useProjectsPage();
  return <ProjectsPageView vm={vm} />;
}

export default function ProjectsListPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <ProjectsListPageInner />
    </Suspense>
  );
}
