"use client";

/** 租户资源配额只读页（链路 §3）。 */

import { SystemQuotaPageView, useSystemQuotaPage } from "@/features/system-quota";

export default function SystemQuotaPage() {
  const vm = useSystemQuotaPage();
  return <SystemQuotaPageView vm={vm} />;
}
