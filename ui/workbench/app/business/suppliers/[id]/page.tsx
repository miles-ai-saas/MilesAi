"use client";

import { useParams } from "next/navigation";
import { SupplierDetailView, useSupplierDetailPage } from "@/features/suppliers";

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useSupplierDetailPage(id);
  return <SupplierDetailView vm={vm} />;
}
