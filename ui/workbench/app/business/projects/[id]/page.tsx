"use client";

import { useParams, useSearchParams } from "next/navigation";
import { ProjectDetailView, useProjectDetailPage, type ProjectDetailTab } from "@/features/projects";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab") as ProjectDetailTab | null;
  const vm = useProjectDetailPage(id, { initialTab: tabParam ?? undefined });
  return <ProjectDetailView vm={vm} />;
}
