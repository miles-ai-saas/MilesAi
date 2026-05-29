"use client";

/** 智能体页 A2A Tab（链路 §3 + §4）。 */
import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { A2aHostFormDialog } from "@/features/agents/components/A2aHostFormDialog";
import { AgentRenameInline } from "@/features/agents/components/AgentRenameInline";
import { A2aPeersPanel } from "@/features/agents/components/A2aPeersPanel";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { agentModeLabel, agentStatusLabel, agentTypeLabel } from "@/features/agents/lib/agent-utils";
import { useAgentMeta } from "@/features/agents/hooks/use-agent-meta";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";

type A2aSubTab = "registry" | "hosts";

const SUB_TABS: { id: A2aSubTab; label: string; hint: string }[] = [
  {
    id: "registry",
    label: "外部登记",
    hint: "登记第三方 Agent Card（/.well-known/agent-card.json），供互联宿主或平台内智能体引用",
  },
  {
    id: "hosts",
    label: "互联宿主",
    hint: "创建对话入口，按 A2A 协议编排已登记的外部 Agent",
  },
];

export function A2aAgentsTab() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const agentMeta = useAgentMeta(ready);
  const [subTab, setSubTab] = useState<A2aSubTab>("hosts");
  const [search, setSearch] = useState("");
  const [hostDialogOpen, setHostDialogOpen] = useState(false);
  const [editingHost, setEditingHost] = useState<Agent | null>(null);

  const hosts = usePagedList(
    useCallback((p, s) => api.listAgents(p, s, "a2a"), []),
    { enabled: ready && subTab === "hosts", resetKey: subTab },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filteredHosts = useMemo(() => filterBySearch(hosts.items, search, (a) => `${a.name} ${a.description ?? ""}`), [hosts.items, search]);

  const sub = SUB_TABS.find((t) => t.id === subTab)!;

  return (
    <>
      <div className="col-span-full flex flex-col gap-3 border-b border-line-soft pb-4">
        <div className="flex flex-wrap gap-2">
          {SUB_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSubTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-sm transition ${
                subTab === t.id ? "bg-brand-light font-medium text-brand" : "text-ink-muted hover:bg-surface-subtle hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <p className="text-sm text-ink-muted">{sub.hint}</p>
        {subTab === "hosts" && (
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索互联宿主"
            className="input-field max-w-xs py-2 text-sm"
          />
        )}
      </div>

      {subTab === "registry" ? (
        <A2aPeersPanel />
      ) : (
        <>
          <AddResourceCard
            label="添加 A2A 互联宿主"
            hint="绑定外部 Agent 成员，对话时由编排模型调度"
            onClick={() => {
              setEditingHost(null);
              setHostDialogOpen(true);
            }}
          />
          {filteredHosts.map((a) => {
            const disabled = a.status !== "enabled";
            return (
              <ResourceItemCard
                key={a.id}
                title={<AgentRenameInline agentId={a.id} name={a.name} prominent onRenamed={() => hosts.reload()} />}
                description={a.description ?? "未填写描述"}
                badge={agentStatusLabel(a.status, agentMeta)}
                muted={disabled}
                meta={
                  <span>
                    {agentTypeLabel(a, agentMeta)} · {agentModeLabel(a)}
                  </span>
                }
                actions={
                  <CardActions
                    actions={[
                      { label: "对话", variant: "primary", disabled, onClick: () => router.push(`/workbench/agents/chat?agent=${a.id}`) },
                      {
                        label: disabled ? "启用" : "禁用",
                        variant: disabled ? "primary" : "danger",
                        onClick: () => {
                          const next = a.status === "enabled" ? "disabled" : "enabled";
                          const verb = next === "disabled" ? "禁用" : "启用";
                          requestConfirm({
                            title: `${verb}互联宿主`,
                            message: (
                              <>
                                确定{verb} <span className="font-medium">{a.name}</span>？
                              </>
                            ),
                            confirmLabel: `确认${verb}`,
                            onConfirm: async () => {
                              await api.updateAgent(a.id, { status: next });
                              await hosts.reload();
                            },
                          });
                        },
                      },
                    ]}
                    onEdit={() => {
                      setEditingHost(a);
                      setHostDialogOpen(true);
                    }}
                    onDelete={() => {
                      requestConfirm({
                        title: "删除互联宿主",
                        message: (
                          <>
                            确定删除 <span className="font-medium">{a.name}</span>？
                          </>
                        ),
                        destructive: true,
                        confirmLabel: "确认删除",
                        onConfirm: async () => {
                          await api.deleteAgent(a.id);
                          await hosts.reload();
                        },
                      });
                    }}
                  />
                }
              />
            );
          })}
          {!hosts.loading && filteredHosts.length === 0 && (
            <p className="col-span-full py-8 text-center text-sm text-ink-muted">暂无互联宿主。请先在「外部登记」同步 Card，再创建宿主。</p>
          )}
          {!hosts.loading && hosts.total > hosts.size ? (
            <div className="col-span-full">
              <ResourceListFooter page={hosts.page} size={hosts.size} total={hosts.total} onPageChange={hosts.setPage} onSizeChange={hosts.setSize} />
            </div>
          ) : null}
        </>
      )}

      <A2aHostFormDialog
        open={hostDialogOpen}
        title={editingHost ? "编辑 A2A 互联宿主" : "新建 A2A 互联宿主"}
        agent={editingHost}
        onClose={() => setHostDialogOpen(false)}
        onSaved={() => hosts.reload()}
      />
      {confirmDialog}
    </>
  );
}
