"use client";

import { ProjectsPageView, useProjectsPage } from "@/features/projects";

export default function ProjectsListPage() {
  const vm = useProjectsPage();
  return <ProjectsPageView vm={vm} />;
}
