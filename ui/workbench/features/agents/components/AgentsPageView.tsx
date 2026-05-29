"use client";

import { A2aAgentsTab } from "@/features/agents/components/A2aAgentsTab";
import { AgentDetailDialog } from "@/features/agents/components/AgentDetailDialog";
import { AgentFormDialog } from "@/features/agents/components/AgentFormDialog";
import { AgentRenameInline } from "@/features/agents/components/AgentRenameInline";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { FilterChip } from "@/components/ui/FilterChip";
import { StatChip } from "@/components/ui/StatChip";
import type { AgentsPageVm } from "@/features/agents/hooks/use-agents-page";
import { agentModeLabel, agentStatusLabel, agentTypeLabel } from "@/features/agents/lib/agent-utils";
import { AGENTS_TAB_DESCRIPTIONS, AGENTS_TAB_ITEMS } from "@/features/agents/lib/agents-page-shared";

export function AgentsPageView({ vm }: { vm: AgentsPageVm }) {
  const {
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
  } = vm;

  return (
    <>
      <ResourceListLayout
        title="智能体"
        description={AGENTS_TAB_DESCRIPTIONS[tab]}
        searchPlaceholder={tab === "a2a" ? undefined : "搜索智能体名称或描述"}
        search={search}
        onSearchChange={setSearch}
        showSearch={tab !== "a2a"}
        loading={tab !== "a2a" && list.loading}
        tabs={AGENTS_TAB_ITEMS}
        activeTab={tab}
        onTabChange={onTabChange}
        headerAction={
          tab !== "a2a" ? (
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="btn-ghost shrink-0 text-sm" disabled={list.loading} onClick={() => void list.reload()}>
                {list.loading ? "刷新中…" : "刷新"}
              </button>
              <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
              <button type="button" className="btn-ghost border border-line text-sm" onClick={() => setTagManageOpen(true)}>
                管理标签
              </button>
            </div>
          ) : undefined
        }
        footer={
          tab !== "a2a" && !list.loading ? (
            <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          ) : null
        }
      >
        {tab === "a2a" ? (
          <A2aAgentsTab />
        ) : (
          <>
            <div className="col-span-full grid gap-3 sm:grid-cols-3">
              <StatChip label="智能体总数" value={String(list.total)} hint={AGENTS_TAB_ITEMS.find((t) => t.key === tab)?.label} />
              <StatChip label="本页已启用" value={String(pageStats.enabled)} hint={`已绑知识库 ${pageStats.withKb}（当前筛选）`} />
              <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索与分类影响" />
            </div>

            <div className="col-span-full rounded-xl border border-line bg-surface-muted/40 p-4">
              <p className="mb-2 text-xs font-medium text-ink-muted">分类</p>
              <div className="flex flex-wrap gap-2">
                {cat.tabs.map((t) => (
                  <FilterChip key={t.key || "all"} active={cat.activeId === t.key} label={t.label} onClick={() => cat.setActiveId(t.key)} />
                ))}
              </div>
            </div>

            <AddResourceCard label="添加智能体" hint="配置模型、知识库、工具；可选内部协同或引用外部 A2A" onClick={openCreate} />

            {!list.loading && filtered.length === 0 && (
              <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的智能体，可调整筛选或新建</p>
            )}

            {filtered.map((a) => {
              const disabled = a.status !== "enabled";
              return (
                <ResourceItemCard
                  key={a.id}
                  title={<AgentRenameInline agentId={a.id} name={a.name} prominent onRenamed={() => list.reload()} />}
                  description={a.description ?? "未填写描述"}
                  badge={agentStatusLabel(a.status, agentMeta)}
                  muted={disabled}
                  meta={
                    <>
                      <span className="text-xs text-ink-muted">
                        {a.category_name ? `${a.category_name} · ` : ""}
                        {agentTypeLabel(a, agentMeta)} · {a.kb_ids.length > 0 ? `知识库 ${a.kb_ids.length}` : "未绑知识库"} · {agentModeLabel(a)}
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
        onRenamed={() => list.reload()}
        onClose={() => setViewingId(null)}
        onEdit={(a) => {
          setViewingId(null);
          openEdit(a);
        }}
        onChat={(a) => {
          setViewingId(null);
          onChat(a);
        }}
        onDesign={onDesign}
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
