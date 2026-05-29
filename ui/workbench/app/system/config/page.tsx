"use client";

/** 系统配置项（链路 §3，壳层 §7）。 */

import { PageHeader } from "@/components/layout/PageHeader";
import { SystemConfigCategoriesSection } from "@/components/system-config/SystemConfigCategoriesSection";
import { SystemConfigInfraSection } from "@/components/system-config/SystemConfigInfraSection";
import { SystemConfigOssSection } from "@/components/system-config/SystemConfigOssSection";
import { useSystemConfigPage } from "@/hooks/use-system-config-page";
import { SYSTEM_CONFIG_PAGE_DESC } from "@/lib/system-config-shared";

export default function SystemConfigPage() {
  const vm = useSystemConfigPage();

  return (
    <div className="w-full space-y-6">
      <PageHeader title="系统配置" description={SYSTEM_CONFIG_PAGE_DESC} />
      <SystemConfigOssSection vm={vm} />
      <SystemConfigInfraSection vm={vm} />
      <SystemConfigCategoriesSection vm={vm} />
      {vm.msg ? <p className="text-sm text-ink-muted">{vm.msg}</p> : null}
    </div>
  );
}
