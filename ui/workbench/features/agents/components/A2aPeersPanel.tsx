"use client";

/** 外部 A2A 对等体登记（链路 §4）。 */

import { A2aPeerCreateDialog } from "@/features/agents/components/A2aPeerCreateDialog";
import { A2aPeerList } from "@/features/agents/components/A2aPeerList";
import { useA2aPeersPanel } from "@/features/agents/hooks/use-a2a-peers-panel";

export function A2aPeersPanel() {
  const vm = useA2aPeersPanel();

  return (
    <>
      {vm.msg ? <p className="col-span-full mb-2 rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs text-ink-muted">{vm.msg}</p> : null}

      <div className="col-span-full mb-2 flex items-center justify-end gap-2">
        <input
          type="search"
          value={vm.search}
          onChange={(e) => vm.setSearch(e.target.value)}
          placeholder="搜索外部 Agent"
          className="input-field w-full max-w-xs py-2 text-sm"
        />
      </div>

      <A2aPeerList vm={vm} />

      <A2aPeerCreateDialog
        dialogOpen={vm.dialogOpen}
        setDialogOpen={vm.setDialogOpen}
        name={vm.name}
        setName={vm.setName}
        description={vm.description}
        setDescription={vm.setDescription}
        baseUrl={vm.baseUrl}
        setBaseUrl={vm.setBaseUrl}
        busy={vm.busy}
        onCreate={vm.onCreate}
        onProbe={vm.onProbe}
      />
      {vm.confirmDialog}
    </>
  );
}
