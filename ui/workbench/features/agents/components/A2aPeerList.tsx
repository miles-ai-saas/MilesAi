"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { a2aPeerStatusLabel } from "@/lib/a2a-labels";
import type { A2aPeersPanelVm } from "@/features/agents/hooks/use-a2a-peers-panel";

type Props = {
  vm: A2aPeersPanelVm;
};

export function A2aPeerList({ vm }: Props) {
  const { a2aMeta, list, filtered, setDialogOpen, onSync, onDelete } = vm;

  return (
    <>
      <AddResourceCard label="登记外部 Agent" hint="填写对方服务根地址，拉取 /.well-known/agent-card.json" onClick={() => setDialogOpen(true)} />

      {filtered.map((p) => (
        <ResourceItemCard
          key={p.id}
          title={p.name}
          description={p.card_display_name ?? p.description ?? p.base_url ?? p.agent_card_url}
          badge={a2aPeerStatusLabel(p.status, a2aMeta)}
          meta={
            <span className="line-clamp-2">
              {p.skills_count > 0 ? `${p.skills_count} 个 skill · ` : ""}
              {p.last_synced_at ? "已同步 Card" : "未同步"}
              {p.last_error ? ` · ${p.last_error}` : ""}
            </span>
          }
          actions={
            <span className="flex flex-wrap gap-2">
              <button
                type="button"
                className="text-xs text-brand hover:underline"
                onClick={(e) => {
                  e.stopPropagation();
                  void onSync(p.id);
                }}
              >
                同步 Card
              </button>
              <button
                type="button"
                className="text-xs text-ink-muted hover:text-danger"
                onClick={(e) => {
                  e.stopPropagation();
                  void onDelete(p);
                }}
              >
                删除
              </button>
            </span>
          }
        />
      ))}

      {!list.loading && filtered.length === 0 ? (
        <p className="col-span-full py-8 text-center text-sm text-ink-muted">暂无外部 Agent。登记后可同步 Agent Card，供后续 A2A 宿主智能体绑定（P2）。</p>
      ) : null}

      {!list.loading && list.total > list.size ? (
        <div className="col-span-full">
          <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        </div>
      ) : null}
    </>
  );
}
