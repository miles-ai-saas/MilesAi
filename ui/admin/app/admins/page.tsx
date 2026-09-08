"use client";

export default function AdminsPage() {
  const vm = useAdminsPage();
  return <AdminsPageView vm={vm} />;
}
import { AdminsPageView, useAdminsPage } from "@/features/admins";
