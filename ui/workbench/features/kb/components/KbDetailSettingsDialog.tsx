"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { KbDetailPageVm } from "@/hooks/use-kb-detail-page";

export function KbDetailSettingsDialog({ vm }: { vm: KbDetailPageVm }) {
  const kb = vm.kb!;
  return (
    <ResourceDialog
      open={vm.settingsOpen}
      title="知识库设置"
      onClose={() => vm.setSettingsOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => vm.setSettingsOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void vm.onSaveSettings()}>
            保存
          </button>
        </>
      }
    >
      <input className="input-field w-full" placeholder="名称" value={vm.editName} onChange={(e) => vm.setEditName(e.target.value)} />
      <input className="input-field w-full" placeholder="描述（可选）" value={vm.editDesc} onChange={(e) => vm.setEditDesc(e.target.value)} />
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-xs text-ink-muted">
          分片大小
          <input
            type="number"
            min={100}
            max={4000}
            className="input-field mt-1 w-full"
            value={vm.editChunkSize}
            onChange={(e) => vm.setEditChunkSize(Number(e.target.value))}
          />
        </label>
        <label className="block text-xs text-ink-muted">
          重叠长度
          <input
            type="number"
            min={0}
            max={500}
            className="input-field mt-1 w-full"
            value={vm.editChunkOverlap}
            onChange={(e) => vm.setEditChunkOverlap(Number(e.target.value))}
          />
        </label>
      </div>
      <label className="block text-xs text-ink-muted">
        检索策略
        <select
          className="input-field mt-1 w-full"
          value={vm.editRetrievalMode}
          onChange={(e) => vm.setEditRetrievalMode(e.target.value as "vector" | "hybrid")}
        >
          {(
            vm.kbMeta?.retrieval_modes ?? [
              { value: "vector", label: "纯语义向量" },
              { value: "hybrid", label: "混合（向量 + 关键词）" },
            ]
          ).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      {vm.editRetrievalMode === "hybrid" ? (
        <label className="block text-xs text-ink-muted">
          混合权重 α（1=偏向量，0=偏关键词）
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            className="input-field mt-1 w-full"
            value={vm.editHybridAlpha}
            onChange={(e) => vm.setEditHybridAlpha(Number(e.target.value))}
          />
        </label>
      ) : null}
      <p className="text-xs text-ink-faint">
        向量化模型 {kb.embedding_model_name ?? "—"}（{kb.embedding_dimension} 维）创建后不可修改。
      </p>
    </ResourceDialog>
  );
}
