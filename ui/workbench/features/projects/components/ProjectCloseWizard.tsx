"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizClosePreview } from "@/lib/types";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

type Step = 1 | 2 | 3;

export function ProjectCloseWizard({ vm, onDone }: { vm: ProjectDetailPageVm; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [preview, setPreview] = useState<BizClosePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [kbId, setKbId] = useState("");
  const [kbs, setKbs] = useState<{ id: string; name: string }[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [confirmDesensitized, setConfirmDesensitized] = useState(false);
  const [skipArchive, setSkipArchive] = useState(false);

  const canClose = vm.project && vm.project.status !== "closed" && vm.project.status !== "cancelled";

  useEffect(() => {
    if (!open) return;
    void api.listKbs(1, 50).then((r) => setKbs(r.items.map((k) => ({ id: k.id, name: k.name }))));
    setLoading(true);
    api.getClosePreview(vm.projectId)
      .then((p) => {
        setPreview(p);
        setSelectedIds(p.archivable_deliverables.map((d) => d.id));
        setSkipArchive(!p.can_archive);
      })
      .finally(() => setLoading(false));
  }, [open, vm.projectId]);

  const reset = () => {
    setStep(1);
    setPreview(null);
    setConfirmDesensitized(false);
    setKbId("");
  };

  const handleClose = () => {
    setOpen(false);
    reset();
  };

  const handleFinish = async () => {
    setLoading(true);
    try {
      const result = await api.executeCloseWizard(vm.projectId, {
        kb_id: skipArchive ? undefined : kbId || undefined,
        deliverable_ids: skipArchive ? [] : selectedIds,
        run_parse: true,
        skip_archive: skipArchive,
        confirm_desensitized: skipArchive || confirmDesensitized,
      });
      alert(skipArchive ? "项目已结项" : `项目已结项，${result.archived_count} 份交付物已入库`);
      await vm.refreshProject();
      handleClose();
      onDone();
    } finally {
      setLoading(false);
    }
  };

  if (!canClose) return null;

  return (
    <>
      <button type="button" className="btn-primary text-sm" onClick={() => setOpen(true)}>
        结项向导
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-ink">结项向导</h2>
            <p className="mt-1 text-xs text-ink-muted">步骤 {step} / 3</p>

            {loading && !preview ? (
              <p className="mt-6 text-sm text-ink-muted">加载检查清单…</p>
            ) : preview ? (
              <>
                {step === 1 && (
                  <div className="mt-4 space-y-3 text-sm">
                    <CheckItem label="未提交交付物" value={preview.pending_deliverables} warn={preview.pending_deliverables > 0} />
                    <CheckItem label="待验收交付物" value={preview.submitted_deliverables} warn={preview.submitted_deliverables > 0} />
                    <CheckItem label="未完成工作包" value={preview.incomplete_work_packages} warn={preview.incomplete_work_packages > 0} />
                    <CheckItem label="可入库交付物" value={preview.archivable_deliverables.length} />
                    {preview.client_confidentiality === "restricted" && (
                      <p className="rounded bg-red-50 p-2 text-xs text-red-600">涉密客户：禁止案例入库</p>
                    )}
                    {preview.client_confidentiality === "internal" && (
                      <p className="rounded bg-yellow-50 p-2 text-xs text-yellow-800">内部客户：入库前请确认已脱敏</p>
                    )}
                  </div>
                )}

                {step === 2 && (
                  <div className="mt-4 space-y-3">
                    {preview.can_archive && !skipArchive ? (
                      <>
                        <label className="block text-sm">
                          <span className="text-xs text-ink-muted">目标知识库</span>
                          <select className="input-field mt-1 w-full text-sm" value={kbId} onChange={(e) => setKbId(e.target.value)}>
                            <option value="">— 选择 —</option>
                            {kbs.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
                          </select>
                        </label>
                        <div className="space-y-2">
                          {preview.archivable_deliverables.map((d) => (
                            <label key={d.id} className="flex items-center gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(d.id)}
                                onChange={(e) => setSelectedIds((ids) => e.target.checked ? [...ids, d.id] : ids.filter((x) => x !== d.id))}
                              />
                              {d.name}{d.version ? ` (${d.version})` : ""}
                            </label>
                          ))}
                        </div>
                        <label className="flex items-start gap-2 text-sm text-ink">
                          <input type="checkbox" checked={confirmDesensitized} onChange={(e) => setConfirmDesensitized(e.target.checked)} className="mt-1" />
                          我已确认所选内容已完成脱敏，可沉淀为案例
                        </label>
                      </>
                    ) : (
                      <p className="text-sm text-ink-muted">{preview.archive_blocked_reason ?? "跳过案例入库"}</p>
                    )}
                    <label className="flex items-center gap-2 text-sm text-ink-muted">
                      <input type="checkbox" checked={skipArchive} onChange={(e) => setSkipArchive(e.target.checked)} />
                      跳过案例入库，直接结项
                    </label>
                  </div>
                )}

                {step === 3 && (
                  <div className="mt-4 space-y-2 text-sm text-ink">
                    <p>即将结项项目：<strong>{preview.project_name}</strong></p>
                    {!skipArchive && selectedIds.length > 0 && kbId && (
                      <p className="text-ink-muted">将入库 {selectedIds.length} 份交付物</p>
                    )}
                    <p className="text-xs text-ink-faint">结项后项目状态变为「已结项」，仍可查看历史数据。</p>
                  </div>
                )}

                <div className="mt-6 flex justify-between gap-2">
                  <button type="button" className="btn-sm-outline text-sm" onClick={handleClose}>取消</button>
                  <div className="flex gap-2">
                    {step > 1 && (
                      <button type="button" className="btn-sm-outline text-sm" onClick={() => setStep((s) => (s - 1) as Step)}>上一步</button>
                    )}
                    {step < 3 ? (
                      <button type="button" className="btn-primary text-sm" onClick={() => setStep((s) => (s + 1) as Step)}>下一步</button>
                    ) : (
                      <button
                        type="button"
                        className="btn-primary text-sm"
                        disabled={loading || (!skipArchive && selectedIds.length > 0 && (!kbId || !confirmDesensitized))}
                        onClick={() => void handleFinish()}
                      >
                        {loading ? "处理中…" : "确认结项"}
                      </button>
                    )}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}

function CheckItem({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={`flex justify-between rounded p-2 ${warn ? "bg-amber-50" : "bg-surface-muted/60"}`}>
      <span className="text-ink-muted">{label}</span>
      <span className={warn ? "font-medium text-amber-700" : "text-ink"}>{value}</span>
    </div>
  );
}
