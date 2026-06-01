"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { BizTableSkeleton } from "@/features/business/components/BizListSkeleton";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";
import {
  CONTRACT_STATUSES,
  CONTRACT_STATUS_LABELS,
  CONTRACT_TYPE_LABELS,
  contractStatusBadgeClass,
} from "@/features/contracts/lib/contract-labels";
import type { BizContract } from "@/lib/types";

function RowActions({ onOpen, onDelete }: { onOpen: () => void; onDelete: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <button type="button" className="text-xs text-brand hover:underline" onClick={onOpen}>
        详情
      </button>
      <button
        type="button"
        className="text-xs text-red-600 hover:underline"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        删除
      </button>
    </div>
  );
}

function ContractMobileCard({
  contract,
  onOpen,
  onDelete,
}: {
  contract: BizContract;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <article
      className="card cursor-pointer p-4 transition hover:border-brand/30 hover:shadow-sm"
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-medium text-ink">{contract.name}</h3>
          <p className="truncate text-xs text-ink-faint">{contract.contract_no || "无编号"}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${contractStatusBadgeClass(contract.status)}`}>
          {CONTRACT_STATUS_LABELS[contract.status] ?? contract.status}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span className="rounded-full bg-surface-muted px-2 py-0.5">
          {CONTRACT_TYPE_LABELS[contract.type] ?? contract.type}
        </span>
        {contract.total_amount != null ? (
          <span className="font-medium text-ink">¥{contract.total_amount.toLocaleString()}</span>
        ) : null}
      </div>
      <div className="mt-3 flex justify-end" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <RowActions onOpen={onOpen} onDelete={onDelete} />
      </div>
    </article>
  );
}

export function ContractsFilters({ vm }: { vm: ContractsPageVm }) {
  const { status, onStatus, clearFilters, hasActiveFilters } = vm;

  return (
    <div className="border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">状态</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !status ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
          }`}
          onClick={() => onStatus("")}
        >
          全部
        </button>
        {CONTRACT_STATUSES.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              status === item.key
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => onStatus(status === item.key ? "" : item.key)}
          >
            {item.label}
          </button>
        ))}
        {hasActiveFilters ? (
          <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function ContractsTable({ vm }: { vm: ContractsPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) {
    return <BizTableSkeleton />;
  }

  if (list.items.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无匹配的合同</p>
        <p className="mt-1 text-xs text-ink-faint">调整状态筛选，或点击右上角新建合同</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {list.items.map((contract) => (
          <ContractMobileCard
            key={contract.id}
            contract={contract}
            onOpen={() => openDetail(contract.id)}
            onDelete={() => onDelete(contract)}
          />
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">合同名称</th>
              <th className="px-4 py-2.5 font-medium">编号</th>
              <th className="px-4 py-2.5 font-medium">金额</th>
              <th className="px-4 py-2.5 font-medium">状态</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.map((contract) => (
              <tr
                key={contract.id}
                className="cursor-pointer transition hover:bg-surface-muted/40"
                onClick={() => openDetail(contract.id)}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-ink">{contract.name}</p>
                  <p className="text-xs text-ink-muted">{CONTRACT_TYPE_LABELS[contract.type] ?? contract.type}</p>
                </td>
                <td className="px-4 py-3 text-xs text-ink-faint">{contract.contract_no || "—"}</td>
                <td className="px-4 py-3 text-sm tabular-nums text-ink-muted">
                  {contract.total_amount != null ? `¥${contract.total_amount.toLocaleString()}` : "—"}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${contractStatusBadgeClass(contract.status)}`}>
                    {CONTRACT_STATUS_LABELS[contract.status] ?? contract.status}
                  </span>
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                  <RowActions onOpen={() => openDetail(contract.id)} onDelete={() => onDelete(contract)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function ContractsListFooter({ vm }: { vm: ContractsPageVm }) {
  const { list } = vm;
  return (
    <ResourceListFooter
      className="border-t border-line px-4 py-3"
      page={list.page}
      size={list.size}
      total={list.total}
      onPageChange={list.setPage}
      onSizeChange={list.setSize}
    />
  );
}
