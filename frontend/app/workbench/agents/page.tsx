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
import { useAgentMeta } from "@/hooks/use-agent-meta";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { useCategoryTabs } from "@/components/category/useCategoryTabs";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { api } from "@/lib/api";
import type { Agent, AgentType } from "@/lib/types";

type AgentsTab = "all" | "custom" | "a2a";

const TAB_ITEMS = [
  { key: "all" as const, label: "全部" },
  { key: "custom" as const, label: "智能体" },
  { key: "a2a" as const, label: "A2A 互联" },
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

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint line-clamp-2">{hint}</p> : null}
    </div>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs transition ${
        active
          ? "bg-brand-light font-medium text-brand"
          : "text-ink-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

export default function AgentsPage() {
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
      (p, s) =>
        api.listAgents(
          p,
          s,
          tab === "all" ? undefined : tabToApiType(tab),
          cat.activeCategoryId,
          tagFilterIds.length ? tagFilterIds : undefined,
        ),
      [tab, cat.activeCategoryId, tagFilterIds],
    ),
    { enabled: ready && tab !== "a2a", resetKey: `${tab}-${cat.activeId}-${tagFilterIds.join(",")}` },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(() => {
    let items = list.items;
    if (tab === "all") {
      items = items.filter((a) => a.agent_type !== "a2a");
    }
    return filterBySearch(items, search, (a) => `${a.name} ${a.description ?? ""}`);
  }, [list.items, search, tab]);

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
    router.push(`/workbench/agents/chat?agent=${agent.id}`);
  };

  return (
    <>
      <ResourceListLayout
        title="智能体"
        description={TAB_DESCRIPTIONS[tab]}
        searchPlaceholder={tab === "a2a" ? undefined : "搜索智能体名称或描述"}
        search={search}
        onSearchChange={setSearch}
        showSearch={tab !== "a2a"}
        loading={tab !== "a2a" && list.loading}
        tabs={TAB_ITEMS}
        activeTab={tab}
        onTabChange={onTabChange}
        headerAction={
          tab !== "a2a" ? (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-ghost shrink-0 text-sm"
                disabled={list.loading}
                onClick={() => void list.reload()}
              >
                {list.loading ? "刷新中…" : "刷新"}
              </button>
              <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
              <button
                type="button"
                className="btn-ghost border border-line text-sm"
                onClick={() => setTagManageOpen(true)}
              >
                管理标签
              </button>
            </div>
          ) : undefined
        }
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
            <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatChip label="智能体总数" value={String(list.total)} hint={TAB_ITEMS.find((t) => t.key === tab)?.label} />
              <StatChip
                label="本页已启用"
                value={String(pageStats.enabled)}
                hint={`已绑知识库 ${pageStats.withKb}（当前筛选）`}
              />
              <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索与分类影响" />
              <StatChip
                label="快捷入口"
                value="对话"
                hint="卡片内可查看、对话、编排配置"
              />
            </div>

            <div className="col-span-full rounded-xl border border-line bg-surface-muted/40 p-4">
              <p className="mb-2 text-xs font-medium text-ink-muted">分类</p>
              <div className="flex flex-wrap gap-2">
                {cat.tabs.map((t) => (
                  <FilterChip
                    key={t.key || "all"}
                    active={cat.activeId === t.key}
                    label={t.label}
                    onClick={() => cat.setActiveId(t.key)}
                  />
                ))}
              </div>
            </div>

            <AddResourceCard
              label="添加智能体"
              hint="配置模型、知识库、工具；可选内部协同或引用外部 A2A"
              onClick={openCreate}
            />

            {!list.loading && filtered.length === 0 && (
              <p className="col-span-full py-12 text-center text-sm text-ink-faint">
                暂无匹配的智能体，可调整筛选或新建
              </p>
            )}

            {filtered.map((a) => {
              const disabled = a.status !== "enabled";
              return (
                <ResourceItemCard
                  key={a.id}
                  title={a.name}
                  description={a.description ?? "未填写描述"}
                  badge={agentStatusLabel(a.status, agentMeta)}
                  muted={disabled}
                  meta={
                    <>
                      <span className="text-xs text-ink-muted">
                        {a.category_name ? `${a.category_name} · ` : ""}
                        {agentTypeLabel(a, agentMeta)} ·{" "}
                        {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length}` : "未绑知识库"} ·{" "}
                        {agentModeLabel(a)}
                      </span>
                      <TagChips tags={a.tags} />
                    </>
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
      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />
      {confirmDialog}
    </>
  );
}
