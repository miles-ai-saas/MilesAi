"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { HooksPageVm } from "@/hooks/use-hooks-page";
import { optionLabel } from "@/lib/enum-meta";
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

export function HookBindingsDialog({ vm }: { vm: HooksPageVm }) {
  const {
    bindingHook,
    setBindingHook,
    bindingsLoading,
    bindings,
    executions,
    triggers,
    scopes,
    bindTrigger,
    setBindTrigger,
    bindScope,
    setBindScope,
    bindTargetId,
    setBindTargetId,
    addBinding,
    removeBinding,
  } = vm;

  return (
    <ResourceDialog
      open={!!bindingHook}
      title={bindingHook ? `${bindingHook.name} · 绑定与执行` : "绑定"}
      size="lg"
      onClose={() => setBindingHook(null)}
      footer={
        <button type="button" className="btn-ghost" onClick={() => setBindingHook(null)}>
          关闭
        </button>
      }
    >
      {bindingsLoading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <div className="space-y-6">
          <section>
            <h3 className="mb-2 text-sm font-medium text-ink">挂载规则</h3>
            <ul className="divide-y rounded-lg border border-line text-sm">
              {bindings.length === 0 && <li className="px-3 py-2 text-ink-faint">暂无绑定</li>}
              {bindings.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <span className="text-xs text-ink-muted">
                    {optionLabel(scopes, b.scope)} · {optionLabel(triggers, b.trigger)}
                    {b.target_id ? ` · ${b.target_id.slice(0, 8)}…` : ""} · 优先级 {b.priority}
                  </span>
                  <button type="button" className="shrink-0 text-xs text-red-600" onClick={() => void removeBinding(b.id)}>
                    删除
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium text-ink">最近执行</h3>
            <ul className="divide-y rounded-lg border border-line text-xs">
              {executions.length === 0 && <li className="px-3 py-2 text-ink-faint">尚无执行记录</li>}
              {executions.map((ex) => (
                <li key={ex.id} className="space-y-0.5 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={ex.status === "ok" ? "text-green-700" : ex.status === "blocked" ? "text-amber-700" : "text-red-600"}>{ex.status}</span>
                    <span className="text-ink-muted">
                      {optionLabel(triggers, ex.trigger)} · {optionLabel(scopes, ex.scope)}
                    </span>
                    {ex.duration_ms != null && <span>{ex.duration_ms}ms</span>}
                    {ex.http_status != null && <span>HTTP {ex.http_status}</span>}
                  </div>
                  {ex.error_message && <p className="truncate text-ink-faint">{ex.error_message}</p>}
                </li>
              ))}
            </ul>
          </section>

          <section className="border-t border-line-soft pt-4">
            <p className="mb-2 text-xs font-medium text-ink-muted">新增绑定</p>
            <select className="input-field mb-2 w-full" value={bindTrigger} onChange={(e) => setBindTrigger(e.target.value)} disabled={!triggers.length}>
              {triggers.map(renderTriggerOption)}
            </select>
            <select className="input-field mb-2 w-full" value={bindScope} onChange={(e) => setBindScope(e.target.value)} disabled={!scopes.length}>
              {scopes.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                  {s.hint ? ` — ${s.hint}` : ""}
                </option>
              ))}
            </select>
            <input
              className="input-field mb-2 w-full font-mono text-xs"
              placeholder="目标 ID（global 可留空）"
              value={bindTargetId}
              onChange={(e) => setBindTargetId(e.target.value)}
            />
            <button type="button" className="btn-primary w-full" onClick={() => void addBinding()}>
              添加绑定
            </button>
          </section>
        </div>
      )}
    </ResourceDialog>
  );
}
