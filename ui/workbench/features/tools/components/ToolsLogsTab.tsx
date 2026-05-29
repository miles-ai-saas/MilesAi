"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { InvocationLogRow, StatChip } from "@/features/tools/components/tool-page-ui";
import type { ToolsPageVm } from "@/features/tools/hooks/use-tools-page";

export function ToolsLogsTab({ vm }: { vm: ToolsPageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索工具编号、状态或错误信息"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.logList.loading}
      footer={
        !vm.logList.loading ? (
          <ResourceListFooter
            page={vm.logList.page}
            size={vm.logList.size}
            total={vm.logList.total}
            onPageChange={vm.logList.setPage}
            onSizeChange={vm.logList.setSize}
          />
        ) : null
      }
    >
      <div className="col-span-full grid gap-3 sm:grid-cols-2">
        <StatChip label="调用记录" value={String(vm.logList.total)} hint="当前租户审计日志总数" />
        <StatChip label="本页展示" value={String(vm.filteredLogs.length)} hint="受搜索筛选影响" />
      </div>
      <div className="col-span-full space-y-3">
        {!vm.logList.loading && vm.filteredLogs.length === 0 && (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无调用记录</p>
        )}
        {vm.filteredLogs.map((log) => (
          <InvocationLogRow key={log.id} log={log} toolsMeta={vm.toolsMeta} />
        ))}
      </div>
    </ResourceListLayout>
  );
}
