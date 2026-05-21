"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { agentModeLabel, buildCreateAgentPayload } from "@/lib/agent-utils";
import { filterBySearch } from "@/lib/filter-search";
import type { Flow, ModelConfig, PromptTemplate } from "@/lib/types";

export default function AgentsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);

  const list = usePagedList(useCallback((p, s) => api.listAgents(p, s), []), { enabled: ready });

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.listFlows(1), api.listPromptTemplates(1), api.listModelConfigs()]).then(
      ([f, p, m]) => {
        setFlows(f.items.filter((x) => x.status === "published"));
        setPrompts(p.items);
        setModels(m);
      },
    );
  }, [ready]);

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (a) => `${a.name} ${a.description ?? ""}`),
    [list.items, search],
  );

  const createAgent = async () => {
    const agent = await api.createAgent(
      buildCreateAgentPayload(list.total, { flows, prompts, models }),
    );
    await list.reload();
    router.push(`/workbench/agents/chat?agent=${agent.id}`);
  };

  return (
    <ResourceListLayout
      title="智能体"
      description="管理智能体配置；知识库为可选项，可按需绑定以增强检索能力。进入对话工作台进行调试与试用。"
      searchPlaceholder="搜索智能体名称"
      search={search}
      onSearchChange={setSearch}
      loading={list.loading}
      headerAction={
        <button type="button" onClick={() => router.push("/workbench/agents/chat")} className="btn-ghost shrink-0">
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
        hint="创建后可进入对话工作台调试"
        onClick={createAgent}
      />
      {filtered.map((a) => (
        <ResourceItemCard
          key={a.id}
          href={`/workbench/agents/chat?agent=${a.id}`}
          title={a.name}
          description={a.description ?? "未填写描述"}
          badge={a.status}
          meta={
            <span>
              {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length} 个` : "未绑知识库"} · {agentModeLabel(a)}
            </span>
          }
        />
      ))}
    </ResourceListLayout>
  );
}
