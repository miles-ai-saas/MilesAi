"use client";

import { Suspense } from "react";
import { ProjectDetailView, useProjectDetailPage } from "@/features/projects";

export default function ProjectDetailPage({ id }: { id: string }) {
  const vm = useProjectDetailPage(id);
  return (
    <Suspense fallback={null}>
      <ProjectDetailView vm={vm} />
    </Suspense>
  );
}
