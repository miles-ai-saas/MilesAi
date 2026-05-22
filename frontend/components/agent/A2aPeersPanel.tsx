"use client";

import { useCallback, useMemo, useState } from "react";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { usePagedList } from "@/hooks/use-paged-list";
import type { A2aPeer } from "@/lib/types";

function peerStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "待同步",
    active: "已连通",
    error: "异常",
    inactive: "已停用",
  };
  return map[status] ?? status;
}

export function A2aPeersPanel() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listA2aPeers(p, s), []), {
    enabled: ready,
  });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (p) => `${p.name} ${p.description ?? ""} ${p.base_url ?? ""}`),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!name.trim() || !baseUrl.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const peer = await api.createA2aPeer({
        name: name.trim(),
        description: description.trim() || undefined,
        base_url: baseUrl.trim(),
      });
      setDialogOpen(false);
      setName("");
      setDescription("");
      setBaseUrl("");
      setMsg(`已登记「${peer.name}」，请点击「同步 Card」拉取 Agent Card`);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "登记失败");
    } finally {
      setBusy(false);
    }
  };

  const onProbe = async () => {
    if (!baseUrl.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await api.probeA2aPeer(baseUrl.trim());
      setMsg(res.ok ? `探测成功：${res.message}` : `探测失败：${res.message}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "探测失败");
    } finally {
      setBusy(false);
    }
  };

  const onSync = async (id: string) => {
    setMsg("");
    try {
      const res = await api.syncA2aPeerCard(id);
      setMsg(res.message);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
    }
  };

  const onDelete = async (peer: A2aPeer) => {
    if (!confirm(`确定删除外部 Agent「${peer.name}」？`)) return;
    await api.deleteA2aPeer(peer.id);
    await list.reload();
  };

  return (
    <>
      {msg ? (
        <p className="col-span-full mb-2 rounded-lg border border-line-soft bg-surface-muted px-3 py-2 text-xs text-ink-muted">
          {msg}
        </p>
      ) : null}

      <div className="col-span-full mb-2 flex items-center justify-end gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索外部 Agent"
          className="input-field w-full max-w-xs py-2 text-sm"
        />
      </div>

      <AddResourceCard
        label="登记外部 Agent"
        hint="填写对方服务根地址，拉取 /.well-known/agent-card.json"
        onClick={() => setDialogOpen(true)}
      />

      {filtered.map((p) => (
        <ResourceItemCard
          key={p.id}
          title={p.name}
          description={p.card_display_name ?? p.description ?? p.base_url ?? p.agent_card_url}
          badge={peerStatusLabel(p.status)}
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
        <p className="col-span-full py-8 text-center text-sm text-ink-muted">
          暂无外部 Agent。登记后可同步 Agent Card，供后续 A2A 宿主智能体绑定（P2）。
        </p>
      ) : null}

      {!list.loading && list.total > list.size ? (
        <div className="col-span-full">
          <ResourceListFooter
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        </div>
      ) : null}

      <ResourceDialog
        open={dialogOpen}
        title="登记外部 A2A Agent"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-sm-outline" disabled={busy} onClick={() => void onProbe()}>
              探测连通
            </button>
            <button type="button" className="btn-sm-outline" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary text-sm"
              disabled={busy || !name.trim() || !baseUrl.trim()}
              onClick={() => void onCreate()}
            >
              {busy ? "提交中…" : "登记"}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">显示名称</span>
            <input
              className="input-field w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：合作伙伴客服 Agent"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">根地址或 Agent Card URL</span>
            <input
              className="input-field w-full font-mono text-xs"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://partner.example.com"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">备注（可选）</span>
            <textarea
              className="input-field w-full resize-none"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <p className="text-xs text-ink-faint">
            将解析为{" "}
            <code className="rounded bg-surface-muted px-1">/.well-known/agent-card.json</code>
            ，与平台内「内部协同」无关。
          </p>
        </div>
      </ResourceDialog>
    </>
  );
}
