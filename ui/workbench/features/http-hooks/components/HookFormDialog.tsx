"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { HooksPageVm } from "@/features/http-hooks/hooks/use-hooks-page";
import type { EnumOption } from "@/lib/types";

function renderTriggerOption(t: EnumOption) {
  return (
    <option key={t.value} value={t.value}>
      {t.label}
      {t.hint ? ` — ${t.hint}` : ""}
      {t.implemented === false ? "（未接线）" : ""}
    </option>
  );
}

export function HookFormDialog({ vm }: { vm: HooksPageVm }) {
  const {
    dialogOpen,
    setDialogOpen,
    editing,
    name,
    setName,
    url,
    setUrl,
    onFailure,
    setOnFailure,
    trigger,
    setTrigger,
    scope,
    setScope,
    triggers,
    scopes,
    onFailureOptions,
    onSaveHook,
  } = vm;

  return (
    <ResourceDialog
      open={dialogOpen}
      title={editing ? "编辑 HTTP 钩子" : "新建 HTTP 钩子"}
      description="接收 JSON 信封；before_* 可响应 action: continue | block | modify"
      onClose={() => setDialogOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onSaveHook()}>
            保存
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <input className="input-field w-full" placeholder="名称，如：访问审计" value={name} onChange={(e) => setName(e.target.value)} />
        <input
          className="input-field w-full font-mono text-sm"
          placeholder="https://your-service/hooks/agent"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-ink-muted">HTTP 失败时（仅 before_*）</span>
          <select className="input-field w-full" value={onFailure} onChange={(e) => setOnFailure(e.target.value)} disabled={!onFailureOptions.length}>
            {onFailureOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {!editing && (
          <>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-ink-muted">默认绑定 · 时机</span>
              <select className="input-field w-full" value={trigger} onChange={(e) => setTrigger(e.target.value)} disabled={!triggers.length}>
                {triggers.map(renderTriggerOption)}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-ink-muted">默认绑定 · 作用域</span>
              <select className="input-field w-full" value={scope} onChange={(e) => setScope(e.target.value)} disabled={!scopes.length}>
                {scopes.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                    {s.hint ? ` — ${s.hint}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
      </div>
    </ResourceDialog>
  );
}
