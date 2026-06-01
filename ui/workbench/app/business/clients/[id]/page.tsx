"use client";

import { useParams } from "next/navigation";
import { ClientDetailView, useClientDetailPage } from "@/features/clients";

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useClientDetailPage(id);
  return <ClientDetailView vm={vm} />;
}
