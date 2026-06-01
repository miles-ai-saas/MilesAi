"use client";

import { SuppliersPageView, useSuppliersPage } from "@/features/suppliers";

export default function SuppliersListPage() {
  const vm = useSuppliersPage();
  return <SuppliersPageView vm={vm} />;
}
