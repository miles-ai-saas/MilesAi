"use client";

/** 智能体只读详情（链路 §4 `useAgentMeta`）。 */

import { AgentDetailDialogBody, AgentDetailDialogFooter } from "@/components/agent/AgentDetailDialogSections";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { useAgentDetailDialog } from "@/hooks/use-agent-detail-dialog";
import type { Agent } from "@/lib/types";

type Props = {
  open: boolean;
  agentId: string | null;
  onClose: () => void;
  onEdit: (agent: Agent) => void;
  onChat: (agent: Agent) => void;
  onDesign: (agent: Agent) => void;
  onRenamed?: () => void;
};

export function AgentDetailDialog({ open, agentId, onClose, onEdit, onChat, onDesign, onRenamed }: Props) {
  const vm = useAgentDetailDialog(open, agentId);

  return (
    <ResourceDialog
      open={open}
      title="查看智能体"
      size="sheet"
      onClose={onClose}
      footer={
        vm.agent && vm.resolved ? (
          <AgentDetailDialogFooter
            agent={vm.agent}
            disabled={vm.resolved.disabled}
            onClose={onClose}
            onEdit={onEdit}
            onChat={onChat}
            onDesign={onDesign}
          />
        ) : (
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
        )
      }
    >
      {vm.loading && <p className="py-8 text-center text-sm text-ink-muted">加载中…</p>}
      {vm.error && <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{vm.error}</p>}
      {vm.agent && !vm.loading && !vm.error && <AgentDetailDialogBody vm={vm} onRenamed={onRenamed} />}
    </ResourceDialog>
  );
}
