"use client";

import Link from "next/link";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { MarketplacePageVm } from "@/features/marketplace/hooks/use-marketplace-page";

export function MarketplaceInstallsView({ vm }: { vm: MarketplacePageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索已安装应用"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.installs.loading}
      footer={
        !vm.installs.loading ? (
          <ResourceListFooter
            page={vm.installs.page}
            size={vm.installs.size}
            total={vm.installs.total}
            onPageChange={vm.installs.setPage}
            onSizeChange={vm.installs.setSize}
          />
        ) : null
      }
    >
      {vm.msg ? <PageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      <div className="col-span-full grid gap-3 sm:grid-cols-2">
        <StatChip label="安装记录" value={String(vm.installs.total)} hint="当前租户历史安装" />
        <StatChip label="本页展示" value={String(vm.installsFiltered.length)} hint="受搜索筛选影响" />
      </div>
      {!vm.installs.loading && vm.installsFiltered.length === 0 ? (
        <p className="col-span-full py-12 text-center text-sm text-ink-faint">尚未安装任何应用，请前往「应用广场」浏览</p>
      ) : null}
      {vm.installsFiltered.map((ins) => {
        const canUpgrade = ins.app_version && ins.installed_version && ins.app_version !== ins.installed_version;
        return (
          <ResourceItemCard
            key={ins.id}
            title={ins.app_name}
            description={`v${ins.installed_version ?? "?"} · 安装于 ${new Date(ins.created_at).toLocaleDateString("zh-CN")}${ins.app_version ? ` · 市场 v${ins.app_version}` : ""}`}
            badge={canUpgrade ? "可升级" : "已安装"}
            actions={
              <span className="flex flex-wrap items-center gap-3 text-xs">
                {canUpgrade ? (
                  <button
                    type="button"
                    className="font-medium text-brand hover:underline disabled:opacity-50"
                    disabled={vm.upgrading === ins.app_id}
                    onClick={() => void vm.onOpenUpgrade(ins)}
                  >
                    {vm.upgrading === ins.app_id ? "升级中…" : "升级到最新版"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="font-medium text-ink-muted hover:text-ink hover:underline disabled:opacity-50"
                  disabled={vm.rollingBack === ins.app_id}
                  onClick={() => void vm.onOpenRollback(ins)}
                >
                  {vm.rollingBack === ins.app_id ? "回滚中…" : "回滚上一版"}
                </button>
                <span className="flex flex-wrap gap-3 text-brand">
                  {ins.kb_id ? (
                    <Link href={`/workbench/kb/${ins.kb_id}`} className="hover:underline">
                      知识库
                    </Link>
                  ) : null}
                  {ins.flow_id ? (
                    <Link href={`/workbench/flows/${ins.flow_id}/edit`} className="hover:underline">
                      流程
                    </Link>
                  ) : null}
                  {ins.agent_id ? (
                    <Link href="/workbench/agents/chat" className="hover:underline">
                      智能体
                    </Link>
                  ) : null}
                </span>
              </span>
            }
          />
        );
      })}
    </ResourceListLayout>
  );
}
