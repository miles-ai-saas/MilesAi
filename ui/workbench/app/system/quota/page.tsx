"use client";

/** 租户资源配额只读页（链路 §3）。 */

import { SystemQuotaPageView } from "@/components/system-quota/SystemQuotaPageView";
import { useSystemQuotaPage } from "@/hooks/use-system-quota-page";

export default function SystemQuotaPage() {
  const vm = useSystemQuotaPage();
  return <SystemQuotaPageView vm={vm} />;
}
