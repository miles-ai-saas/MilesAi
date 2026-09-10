"use client";

import type { RiskPageVm } from "@/features/risk/hooks/use-risk-page";

export function RiskRateLimitEditDialog({ vm }: { vm: RiskPageVm }) {
  const { editRule, setEditRule, editForm, setEditForm, onSaveRule } = vm;
  if (!editRule) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="card w-full max-w-md p-5">
        <h3 className="font-semibold text-ink">编辑限流规则</h3>
        <div className="mt-3 grid gap-2">
          <input className="input-field" placeholder="规则名称" value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
          <input
            className="input-field"
            placeholder="路径模式"
            value={editForm.path_pattern}
            onChange={(e) => setEditForm((f) => ({ ...f, path_pattern: e.target.value }))}
          />
          <input
            className="input-field"
            type="number"
            min={1}
            placeholder="每分钟上限"
            value={editForm.limit_per_minute}
            onChange={(e) => setEditForm((f) => ({ ...f, limit_per_minute: e.target.value }))}
          />
          <textarea
            className="input-field min-h-[72px] resize-y"
            placeholder="说明（可选）"
            value={editForm.description}
            onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
          />
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setEditRule(null)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onSaveRule()}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
