"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { AgentSchedule } from "@/lib/types";

export function useAgentSchedulePanel(agentId: string) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AgentSchedule | null>(null);
  const [msg, setMsg] = useState("");

  const list = usePagedList(
    useCallback((page, size) => api.listAgentSchedules(agentId, page, size), [agentId]),
    { resetKey: agentId },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const enabledOnPage = useMemo(() => list.items.filter((s) => s.enabled).length, [list.items]);

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (schedule: AgentSchedule) => {
    setEditing(schedule);
    setDialogOpen(true);
  };

  const onToggleEnabled = async (schedule: AgentSchedule) => {
    setMsg("");
    try {
      await api.updateAgentSchedule(agentId, schedule.id, { enabled: !schedule.enabled });
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "更新失败");
    }
  };

  const onDelete = (schedule: AgentSchedule) => {
    const preview = schedule.content.trim().length > 80 ? `${schedule.content.trim().slice(0, 80)}…` : schedule.content.trim();
    requestConfirm({
      title: "删除定时任务",
      message: (
        <>
          确定删除该定时任务？
          {preview && <span className="mt-1 block text-ink-muted">{preview}</span>}
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteAgentSchedule(agentId, schedule.id);
        await list.reload();
      },
    });
  };

  return {
    list,
    dialogOpen,
    setDialogOpen,
    editing,
    msg,
    enabledOnPage,
    confirmDialog,
    openCreate,
    openEdit,
    onToggleEnabled,
    onDelete,
  };
}

export type AgentSchedulePanelVm = ReturnType<typeof useAgentSchedulePanel>;
