"use client";

/** 外部 A2A 对等体登记（链路 §4）。 */

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { useA2aPeersPanel } from "@/features/agents/hooks/use-a2a-peers-panel";
import { a2aPeerStatusLabel } from "@/features/agents/lib/a2a-labels";

export function A2aPeersPanel() {
  const vm = useA2aPeersPanel();
  const { a2aMeta, list, filtered, setDialogOpen, onSync, onDelete } = vm;

  return (
    <>
      {vm.msg ? <p className="col-span-full mb-2 rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs text-ink-muted">{vm.msg}</p> : null}

      <div className="col-span-full mb-2 flex items-center justify-end gap-2">
        <input
          type="search"
          value={vm.search}
          onChange={(e) => vm.setSearch(e.target.value)}
          placeholder="搜索外部 Agent"
          className="input-field w-full max-w-xs py-2 text-sm"
        />
      </div>

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

      <ResourceDialog
        open={vm.dialogOpen}
        title="登记外部 A2A Agent"
        onClose={() => vm.setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-sm-outline" disabled={vm.busy} onClick={() => void vm.onProbe()}>
              探测连通
            </button>
            <button type="button" className="btn-sm-outline" onClick={() => vm.setDialogOpen(false)}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary text-sm"
              disabled={vm.busy || !vm.name.trim() || !vm.baseUrl.trim()}
              onClick={() => void vm.onCreate()}
            >
              {vm.busy ? "提交中…" : "登记"}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">显示名称</span>
            <input className="input-field w-full" value={vm.name} onChange={(e) => vm.setName(e.target.value)} placeholder="例如：合作伙伴客服 Agent" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">根地址或 Agent Card URL</span>
            <input
              className="input-field w-full font-mono text-xs"
              value={vm.baseUrl}
              onChange={(e) => vm.setBaseUrl(e.target.value)}
              placeholder="https://partner.example.com"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">API Key（可选）</span>
            <input
              className="input-field w-full font-mono text-xs"
              type="password"
              value={vm.apiKey}
              onChange={(e) => vm.setApiKey(e.target.value)}
              placeholder="对方要求鉴权时填写，作为 X-API-Key 发送"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">备注（可选）</span>
            <textarea className="input-field w-full resize-none" rows={2} value={vm.description} onChange={(e) => vm.setDescription(e.target.value)} />
          </label>
          <p className="text-xs text-ink-faint">
            将解析为 <code className="rounded bg-surface-muted px-1">/.well-known/agent-card.json</code>
            ，与平台内「内部协同」无关；同步 Card 与调用时自动携带上述 API Key。
          </p>
        </div>
      </ResourceDialog>
      {vm.confirmDialog}
    </>
  );
}
