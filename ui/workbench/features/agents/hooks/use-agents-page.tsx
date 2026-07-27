"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useCategoryTabs } from "@/components/category/useCategoryTabs";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { useAgentMeta } from "@/features/agents/hooks/use-agent-meta";
import { pushAgentsChatForAgent } from "@/features/agents/lib/agents-chat-href";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import type { Agent, AgentType } from "@/lib/types";

export type AgentsTab = "all" | "custom" | "a2a";

export const AGENTS_TAB_ITEMS = [
  { key: "all" as const, label: "全部" },
  { key: "custom" as const, label: "智能体" },
  { key: "a2a" as const, label: "A2A 互联" },
];

function agentsTabToApiType(tab: AgentsTab): AgentType | undefined {
  if (tab === "all" || tab === "custom") return "custom";
  if (tab === "a2a") return "a2a";
  return undefined;
}

export function useAgentsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const agentMeta = useAgentMeta(ready);
  const [tab, setTab] = useState<AgentsTab>("custom");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const cat = useCategoryTabs("agent");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const list = usePagedList(
    useCallback(
      (p, s) => api.listAgents(p, s, agentsTabToApiType(tab), cat.activeCategoryId, tagFilterIds.length ? tagFilterIds : undefined),
      [tab, cat.activeCategoryId, tagFilterIds],
    ),
    { enabled: ready && tab !== "a2a", resetKey: `${tab}-${cat.activeId}-${tagFilterIds.join(",")}` },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(() => {
    return filterBySearch(list.items, search, (a) => `${a.name} ${a.description ?? ""}`);
  }, [list.items, search]);

  const pageStats = useMemo(() => {
    let enabled = 0;
    let withKb = 0;
    for (const a of filtered) {
      if (a.status === "enabled") enabled += 1;
      if (a.kb_ids.length > 0) withKb += 1;
    }
    return { enabled, withKb };
  }, [filtered]);

  const onTabChange = (key: string) => {
    setTab(key as AgentsTab);
    setSearch("");
  };

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (agent: Agent) => {
    if (agent.agent_type === "a2a") return;
    setEditing(agent);
    setDialogOpen(true);
  };

  const onDelete = (agent: Agent) => {
    requestConfirm({
      title: "删除智能体",
      message: (
        <>
          确定删除智能体 <span className="font-medium">{agent.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteAgent(agent.id);
        await list.reload();
      },
    });
  };

  const onToggleStatus = (agent: Agent) => {
    const next = agent.status === "enabled" ? "disabled" : "enabled";
    const verb = next === "disabled" ? "禁用" : "启用";
    requestConfirm({
      title: `${verb}智能体`,
      message: (
        <>
          确定{verb}智能体 <span className="font-medium">{agent.name}</span>？
        </>
      ),
      confirmLabel: `确认${verb}`,
      onConfirm: async () => {
        await api.updateAgent(agent.id, { status: next });
        await list.reload();
      },
    });
  };

  const onChat = (agent: Agent) => {
    pushAgentsChatForAgent(router, agent.id);
  };

  const onDesign = (agent: Agent) => {
    setViewingId(null);
    pushAgentsChatForAgent(router, agent.id, { tab: "config" });
  };

  return {
    router,
    agentMeta,
    tab,
    onTabChange,
    search,
    setSearch,
    list,
    filtered,
    pageStats,
    cat,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    dialogOpen,
    setDialogOpen,
    editing,
    viewingId,
    setViewingId,
    confirmDialog,
    openCreate,
    openEdit,
    onDelete,
    onToggleStatus,
    onChat,
    onDesign,
  };
}

export type AgentsPageVm = ReturnType<typeof useAgentsPage>;
