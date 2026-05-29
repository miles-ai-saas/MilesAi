"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { A2aPeersPanelVm } from "@/features/agents/hooks/use-a2a-peers-panel";

type Props = Pick<
  A2aPeersPanelVm,
  | "dialogOpen"
  | "setDialogOpen"
  | "name"
  | "setName"
  | "description"
  | "setDescription"
  | "baseUrl"
  | "setBaseUrl"
  | "busy"
  | "onCreate"
  | "onProbe"
>;

export function A2aPeerCreateDialog({
  dialogOpen,
  setDialogOpen,
  name,
  setName,
  description,
  setDescription,
  baseUrl,
  setBaseUrl,
  busy,
  onCreate,
  onProbe,
}: Props) {
  return (
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
          <button type="button" className="btn-primary text-sm" disabled={busy || !name.trim() || !baseUrl.trim()} onClick={() => void onCreate()}>
            {busy ? "提交中…" : "登记"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1 block text-ink-muted">显示名称</span>
          <input className="input-field w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：合作伙伴客服 Agent" />
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
          <textarea className="input-field w-full resize-none" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <p className="text-xs text-ink-faint">
          将解析为 <code className="rounded bg-surface-muted px-1">/.well-known/agent-card.json</code>
          ，与平台内「内部协同」无关。
        </p>
      </div>
    </ResourceDialog>
  );
}
