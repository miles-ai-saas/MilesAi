"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { copyText } from "@/features/agents/lib/agent-trace";
import type { AgentApiKey, AgentApiKeyCreated } from "@/lib/types";

function CopyButton({ label, copied, onClick, className = "" }: { label: string; copied: boolean; onClick: () => void; className?: string }) {
  return (
    <button type="button" className={`btn-sm-outline shrink-0 ${className}`} onClick={onClick}>
      {copied ? "已复制" : label}
    </button>
  );
}

type Props = {
  agentId: string;
  onDemoKeyChange: (key: string) => void;
  setError: (err: string | null) => void;
};

export function AgentApiKeyCard({ agentId, onDemoKeyChange, setError }: Props) {
  const [keys, setKeys] = useState<AgentApiKey[]>([]);
  const [keyName, setKeyName] = useState("生产");
  const [created, setCreated] = useState<AgentApiKeyCreated | null>(null);
  const [keysLoading, setKeysLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const reloadKeys = useCallback(async () => {
    setKeysLoading(true);
    try {
      const items = await api.listAgentApiKeys(agentId, true);
      setKeys(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载密钥失败");
    } finally {
      setKeysLoading(false);
    }
  }, [agentId, setError]);

  useEffect(() => {
    void reloadKeys();
  }, [reloadKeys]);

  const copy = async (label: string, text: string) => {
    const ok = await copyText(text);
    if (ok) {
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } else {
      setError("复制失败");
    }
  };

  const onCreate = async () => {
    if (!keyName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.createAgentApiKey(agentId, keyName.trim());
      setCreated(out);
      onDemoKeyChange(out.secret);
      await reloadKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const onRevoke = async (keyId: string) => {
    if (!window.confirm("确定吊销该密钥？吊销后立即失效不可恢复。")) return;
    setBusy(true);
    setError(null);
    try {
      await api.revokeAgentApiKey(agentId, keyId);
      await reloadKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "吊销失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {created && (
        <div className="shrink-0 border-b border-amber-200 bg-amber-50/90 px-6 py-3 text-xs text-amber-950">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 space-y-1">
              <p className="font-medium">密钥已创建，请立即复制明文（仅显示一次）</p>
              <code className="block break-all font-mono text-[11px]">{created.secret}</code>
              <p className="text-amber-900/80">{created.warning}</p>
            </div>
            <div className="flex gap-2">
              <CopyButton label="复制密钥" copied={copied === "secret"} onClick={() => void copy("secret", created.secret)} />
              <button type="button" className="btn-sm-outline" onClick={() => setCreated(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
      <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-4 py-2.5">
          <h3 className="text-sm font-medium text-ink">API Key</h3>
        </div>
        <div className="space-y-3 p-4">
          <div className="flex flex-wrap gap-2">
            <input
              className="input-field min-w-[8rem] flex-1 text-sm"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="密钥名称"
              maxLength={64}
            />
            <button type="button" className="btn-sm-primary shrink-0" disabled={busy || !keyName.trim()} onClick={() => void onCreate()}>
              {busy ? "创建中…" : "创建"}
            </button>
          </div>
          {keysLoading ? (
            <p className="text-xs text-ink-muted">加载中…</p>
          ) : keys.length === 0 ? (
            <p className="rounded-lg border border-dashed border-line-soft bg-surface-subtle/60 px-3 py-4 text-xs text-ink-muted">尚无密钥</p>
          ) : (
            <ul className="divide-y divide-line-soft rounded-lg border border-line-soft text-xs">
              {keys.map((k) => (
                <li key={k.id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-ink">{k.name}</p>
                    <p className="font-mono text-[11px] text-ink-muted">
                      mil_{k.key_prefix}…
                      <span className={`ml-2 ${k.status === "active" ? "text-emerald-700" : "text-ink-faint"}`}>{k.status === "active" ? "有效" : "已吊销"}</span>
                    </p>
                  </div>
                  {k.status === "active" && (
                    <button type="button" className="btn-sm-outline shrink-0 text-red-600" disabled={busy} onClick={() => void onRevoke(k.id)}>
                      吊销
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
