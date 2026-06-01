"use client";

import { useParams } from "next/navigation";
import { OpportunityDetailView, useOpportunityDetailPage } from "@/features/opportunities";

export default function OpportunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useOpportunityDetailPage(id);
  return <OpportunityDetailView vm={vm} />;
}
