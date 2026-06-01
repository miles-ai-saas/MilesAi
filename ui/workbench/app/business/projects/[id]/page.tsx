"use client";

import { useParams } from "next/navigation";
import { ProjectDetailView, useProjectDetailPage } from "@/features/projects";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useProjectDetailPage(id);
  return <ProjectDetailView vm={vm} />;
}
