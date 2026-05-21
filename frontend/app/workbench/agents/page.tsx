"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentFormDialog } from "@/components/agent/AgentFormDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { usePagedList } from "@/hooks/use-paged-list";
import { agentModeLabel } from "@/lib/agent-utils";
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
        {filtered.map((a) => (
          <ResourceItemCard
            key={a.id}
            title={a.name}
            description={a.description ?? "未填写描述"}
            badge={a.status}
            meta={
              <span>
                {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length} 个` : "未绑知识库"} ·{" "}
                {agentModeLabel(a)}
              </span>
            }
            actions={
              <CardActions
                onEdit={() => openEdit(a)}
                onDelete={() => onDelete(a)}
              />
            }
          />
        ))}
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
