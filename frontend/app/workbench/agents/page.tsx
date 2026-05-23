"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { A2aAgentsTab } from "@/components/agent/A2aAgentsTab";
import { AgentDetailDialog } from "@/components/agent/AgentDetailDialog";
import { AgentFormDialog } from "@/components/agent/AgentFormDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { agentModeLabel, agentStatusLabel, agentTypeLabel } from "@/lib/agent-utils";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { api } from "@/lib/api";
import type { Agent, AgentType } from "@/lib/types";

type AgentsTab = "all" | "custom" | "a2a";

const TAB_ITEMS: { id: AgentsTab; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "custom", label: "智能体" },
  { id: "a2a", label: "A2A 互联" },
];

const TAB_DESCRIPTIONS: Record<AgentsTab, string> = {
  all: "查看全部平台内智能体（不含 A2A 互联宿主）；A2A 能力请在「A2A 互联」Tab 管理。",
  custom:
    "配置模型、知识库与工具；可选内部协同，或引用已登记的外部 A2A（规则触发 + 自动规划）。",
  a2a: "管理 A2A 协议能力：先在「外部登记」同步 Agent Card，再创建「互联宿主」作为统一对话入口。",
};

function tabToApiType(tab: AgentsTab): AgentType | undefined {
  if (tab === "custom") return "custom";
  if (tab === "a2a") return "a2a";
  return undefined;
}

export default function AgentsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<AgentsTab>("custom");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);

  const list = usePagedList(
    useCallback(
      (p, s) => api.listAgents(p, s, tab === "all" ? undefined : tabToApiType(tab)),
      [tab],
    ),
    { enabled: ready && tab !== "a2a", resetKey: tab },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(() => {
    let items = list.items;
    if (tab === "all") {
      items = items.filter((a) => a.agent_type !== "a2a");
    }
    return filterBySearch(items, search, (a) => `${a.name} ${a.description ?? ""}`);
  }, [list.items, search, tab]);

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
    router.push(`/workbench/agents/chat?agent=${agent.id}`);
  };

  return (
    <>
      <ResourceListLayout
        title="智能体"
        description={TAB_DESCRIPTIONS[tab]}
        searchPlaceholder={tab === "a2a" ? undefined : "搜索智能体名称"}
        search={search}
        onSearchChange={setSearch}
        showSearch={tab !== "a2a"}
        loading={tab !== "a2a" && list.loading}
        tabs={TAB_ITEMS.map((t) => ({ key: t.id, label: t.label }))}
        activeTab={tab}
        onTabChange={(key) => setTab(key as AgentsTab)}
        footer={
          tab !== "a2a" && !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        {tab === "a2a" ? (
          <A2aAgentsTab />
        ) : (
          <>
            <AddResourceCard
              label="添加智能体"
              hint="配置模型、知识库、工具；可选内部协同或引用外部 A2A"
              onClick={openCreate}
            />
            {filtered.map((a) => {
              const disabled = a.status !== "enabled";
              return (
                <ResourceItemCard
                  key={a.id}
                  title={a.name}
                  description={a.description ?? "未填写描述"}
                  badge={agentStatusLabel(a.status)}
                  muted={disabled}
                  meta={
                    <span>
                      {agentTypeLabel(a)} ·{" "}
                      {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length}` : "未绑知识库"} ·{" "}
                      {agentModeLabel(a)}
                    </span>
                  }
                  actions={
                    <CardActions
                      actions={[
                        { label: "查看", onClick: () => setViewingId(a.id) },
                        {
                          label: "对话",
                          variant: "primary",
                          disabled,
                          onClick: () => onChat(a),
                        },
                        {
                          label: disabled ? "启用" : "禁用",
                          variant: disabled ? "primary" : "danger",
                          onClick: () => onToggleStatus(a),
                        },
                      ]}
                      onEdit={() => openEdit(a)}
                      onDelete={() => onDelete(a)}
                    />
                  }
                />
              );
            })}
          </>
        )}
      </ResourceListLayout>

      <AgentDetailDialog
        open={Boolean(viewingId)}
        agentId={viewingId}
        onClose={() => setViewingId(null)}
        onEdit={(a) => {
          setViewingId(null);
          openEdit(a);
        }}
        onChat={(a) => {
          setViewingId(null);
          onChat(a);
        }}
        onDesign={(a) => {
          setViewingId(null);
          router.push(`/workbench/agents/chat?agent=${a.id}&tab=config`);
        }}
      />

      <AgentFormDialog
        open={dialogOpen}
        title={editing ? "编辑智能体" : "新建智能体"}
        agent={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={() => list.reload()}
      />
      {confirmDialog}
    </>
  );
}
