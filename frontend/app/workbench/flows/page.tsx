"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { RAG_TEMPLATE } from "@/lib/flow-nodes";
import { flowStatusLabel } from "@/lib/flow-labels";
import { filterBySearch } from "@/lib/filter-search";
import { useFlowMeta } from "@/hooks/use-flow-meta";

export default function FlowsPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const flowMeta = useFlowMeta(ready);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  const list = usePagedList(useCallback((p, s) => api.listFlows(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (f) => `${f.name} ${f.description ?? ""}`),
    [list.items, search],
  );

  const createRagFlow = async () => {
    setCreating(true);
    try {
      const flow = await api.createFlow("RAG 问答流程", RAG_TEMPLATE);
      router.push(`/workbench/flows/${flow.id}/edit`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <ResourceListLayout
      title="流程编排"
      description="可视化编排智能体执行流程，支持 RAG、工具调用等节点，发布后可绑定智能体。"
      searchPlaceholder="搜索流程名称"
      search={search}
      onSearchChange={setSearch}
      loading={!ready || list.loading}
      footer={
        ready && !list.loading ? (
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
        label="添加新流程"
        hint={creating ? "创建中…" : "从 RAG 模板快速创建"}
        onClick={createRagFlow}
      />
      {filtered.map((flow) => (
        <ResourceItemCard
          key={flow.id}
          href={`/workbench/flows/${flow.id}/edit`}
          title={flow.name}
          description={flow.description ?? "点击进入画布编辑"}
          badge={flowStatusLabel(flow.status, flowMeta)}
          meta={
            <span>
              版本 v{flow.current_version} · <span className="text-brand">编辑画布 →</span>
            </span>
          }
        />
      ))}
    </ResourceListLayout>
  );
}
