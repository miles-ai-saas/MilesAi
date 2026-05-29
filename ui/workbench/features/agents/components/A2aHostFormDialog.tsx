"use client";

/** A2A 互联宿主表单（链路 §4 `useA2aMeta`）。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  A2aHostFormBasicStep,
  A2aHostFormModelStep,
  A2aHostFormPeersStep,
} from "@/features/agents/components/A2aHostFormDialogSections";
import { useA2aHostFormDialog } from "@/features/agents/hooks/use-a2a-host-form-dialog";
import type { Agent } from "@/lib/types";

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

export function A2aHostFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const vm = useA2aHostFormDialog({ open, agent, onClose, onSaved });

  return (
    <ResourceDialog
      open={open}
      title={title}
      size="sheet"
      onClose={onClose}
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">
            <button type="button" className="btn-ghost border border-line" disabled={vm.step === 0} onClick={() => vm.setStep((s) => Math.max(0, s - 1))}>
              上一步
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={vm.busy || !vm.canNext || (vm.isLastStep && vm.form.a2a_peers.length < 1)}
              onClick={vm.goNext}
            >
              {vm.busy ? "保存中…" : vm.isLastStep ? (agent ? "保存" : "创建") : "下一步"}
            </button>
          </div>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
        </div>
      }
    >
      <div className="mx-auto max-w-2xl space-y-6 py-4">
        <p className="text-xs text-ink-muted">
          步骤 {vm.step + 1}/{vm.steps.length} · {vm.steps[vm.step].title}
        </p>
        {vm.step === 0 && <A2aHostFormBasicStep form={vm.form} setForm={vm.setForm} />}
        {vm.step === 1 && <A2aHostFormModelStep form={vm.form} setForm={vm.setForm} models={vm.models} prompts={vm.prompts} />}
        {vm.step === 2 && (
          <A2aHostFormPeersStep
            form={vm.form}
            setForm={vm.setForm}
            a2aPeers={vm.a2aPeers}
            invokePolicies={vm.invokePolicies}
            togglePeer={vm.togglePeer}
            setKeywords={vm.setKeywords}
          />
        )}
      </div>
    </ResourceDialog>
  );
}
