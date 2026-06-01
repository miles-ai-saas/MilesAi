"use client";

/** 客户列表页。 */

import { ClientsPageView, useClientsPage } from "@/features/clients";

export default function ClientsListPage() {
  const vm = useClientsPage();
  return <ClientsPageView vm={vm} />;
}
