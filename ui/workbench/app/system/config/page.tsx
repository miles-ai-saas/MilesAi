"use client";

/** 系统配置项（链路 §3，壳层 §7）。 */

import {
  SystemConfigCategoriesSection,
  SystemConfigInfraSection,
  SystemConfigOssSection,
  useSystemConfigPage,
} from "@/features/system-config";
import { PageHeader } from "@/components/layout/PageHeader";
import { SYSTEM_CONFIG_PAGE_DESC } from "@/features/system-config/lib/system-config-shared";

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
