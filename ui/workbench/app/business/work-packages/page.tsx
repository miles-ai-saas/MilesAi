"use client";

import { WorkPackagesKanbanView, useWorkPackagesPage } from "@/features/work-packages";

export default function BusinessWorkPackagesPage() {
  const vm = useWorkPackagesPage();
  return <WorkPackagesKanbanView vm={vm} />;
}
