"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentDetailDialog } from "@/components/agent/AgentDetailDialog";
import { AgentFormDialog } from "@/components/agent/AgentFormDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { usePagedList } from "@/hooks/use-paged-list";
import { agentModeLabel, agentStatusLabel } from "@/lib/agent-utils";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";

export default function AgentsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);

  const list = usePagedList(useCallback((p, s) => api.listAgents(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (a) => `${a.name} ${a.description ?? ""}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (agent: Agent) => {
    setEditing(agent);
    setDialogOpen(true);
  };

  const onDelete = async (agent: Agent) => {
    if (!confirm(`确定删除智能体「${agent.name}」？`)) return;
    await api.deleteAgent(agent.id);
    await list.reload();
  };

  const onToggleStatus = async (agent: Agent) => {
    const next = agent.status === "enabled" ? "disabled" : "enabled";
    const verb = next === "disabled" ? "禁用" : "启用";
    if (!confirm(`确定${verb}智能体「${agent.name}」？`)) return;
    await api.updateAgent(agent.id, { status: next });
    await list.reload();
  };

  const onChat = (agent: Agent) => {
    router.push(`/workbench/agents/chat?agent=${agent.id}`);
  };

  const onView = (agent: Agent) => {
    setViewingId(agent.id);
  };

  const closeView = () => setViewingId(null);

  return (
    <>
      <ResourceListLayout
        title="智能体"
        description="管理智能体配置；知识库为可选项，可按需绑定以增强检索能力。"
        searchPlaceholder="搜索智能体名称"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        headerAction={
          <button
            type="button"
            onClick={() => router.push("/workbench/agents/chat")}
            className="btn-ghost shrink-0"
          >
            对话工作台
          </button>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        <AddResourceCard
          label="添加新智能体"
          hint="配置模型、知识库与提示词"
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
                  {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length} 个` : "未绑知识库"} ·{" "}
                  {agentModeLabel(a)}
                  {a.published_flow_id ? " · 已绑流程" : ""}
                </span>
              }
              actions={
                <CardActions
                  actions={[
                    {
                      label: "查看",
                      onClick: () => onView(a),
                    },
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
      </ResourceListLayout>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          className="btn-primary"
          onClick={() => router.push("/workbench/agents/chat")}
        >
          进入对话工作台
        </button>
      </div>

      <AgentDetailDialog
        open={Boolean(viewingId)}
        agentId={viewingId}
        onClose={closeView}
        onEdit={(a) => {
          closeView();
          openEdit(a);
        }}
        onChat={(a) => {
          closeView();
          onChat(a);
        }}
        onDesign={(a) => {
          closeView();
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
    </>
  );
}
