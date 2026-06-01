"use client";

import { OpportunitiesPageView, useOpportunitiesPage } from "@/features/opportunities";

export default function OpportunitiesListPage() {
  const vm = useOpportunitiesPage();
  return <OpportunitiesPageView vm={vm} />;
}
