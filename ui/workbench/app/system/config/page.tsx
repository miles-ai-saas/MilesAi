"use client";

/** 系统配置项（链路 §3，壳层 §7）。 */

import {
  SystemConfigCategoriesSection,
  SystemConfigInfraSection,
  SystemConfigOssSection,
  useSystemConfigPage,
} from "@/features/system-config";
import { PageHeader } from "@/components/layout/PageHeader";

const SYSTEM_CONFIG_PAGE_DESC =
  "L2 业务参数可在此编辑；L1 部署连接（PostgreSQL / Redis / 对象存储等）来自环境变量，只读展示。";

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
