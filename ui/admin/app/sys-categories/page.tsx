"use client";

export default function SysCategoriesPage() {
  const vm = useSysCategoriesPage();
  return <SysCategoriesPageView vm={vm} />;
}
import { SysCategoriesPageView, useSysCategoriesPage } from "@/features/sys-categories";
