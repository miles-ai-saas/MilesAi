"use client";

import { AdminsPageView } from "@/components/admins/AdminsPageView";
import { useAdminsPage } from "@/hooks/use-admins-page";

export default function AdminsPage() {
  const vm = useAdminsPage();
  return <AdminsPageView vm={vm} />;
}
