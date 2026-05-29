"use client";

import { SysCategoriesPageView } from "@/components/sys-categories/SysCategoriesPageView";
import { useSysCategoriesPage } from "@/hooks/use-sys-categories-page";

export default function SysCategoriesPage() {
  const vm = useSysCategoriesPage();
  return <SysCategoriesPageView vm={vm} />;
}
