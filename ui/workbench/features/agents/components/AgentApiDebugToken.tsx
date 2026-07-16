"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { copyText } from "@/features/agents/lib/agent-trace";
import type { AgentDebugToken } from "@/lib/types";

function CopyButton({ label, copied, onClick, className = "" }: { label: string; copied: boolean; onClick: () => void; className?: string }) {
  return (
    <button type="button" className={`btn-sm-outline shrink-0 ${className}`} onClick={onClick}>
      {copied ? "已复制" : label}
    </button>
  );
}

function maskToken(token: string): string {
  if (token.length <= 16) return "••••••••••••";
  return `${token.slice(0, 10)}…${token.slice(-6)}`;
}

type Props = {
  agentId: string;
  setError: (err: string | null) => void;
};

export function AgentApiDebugToken({ agentId, setError }: Props) {
  const [token, setToken] = useState<AgentDebugToken | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (label: string, text: string) => {
    const ok = await copyText(text);
    if (ok) {
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } else {
      setError("复制失败");
    }
  };

  const onMint = async () => {
    setBusy(true);
    setError(null);
    try {
      const out = await api.createAgentDebugToken(agentId);
      setToken(out);
      setRevealed(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "签发失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="rounded-xl border border-line bg-surface shadow-card">
      <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-ink-muted marker:content-none">
        调试 Token（等同登录态，勿用于生产）
      </summary>
      <div className="space-y-3 border-t border-line-soft p-4 text-xs">
        <button type="button" className="btn-sm-outline" disabled={busy} onClick={() => void onMint()}>
          {busy ? "生成中…" : token ? "重新生成" : "生成调试 Token"}
        </button>
        {token && (
          <div className="space-y-2 rounded-lg border border-line-soft bg-surface-subtle/80 p-3">
            <div className="flex justify-between gap-2">
              <code className="break-all">{revealed ? token.access_token : maskToken(token.access_token)}</code>
              <div className="flex shrink-0 gap-1">
                <button type="button" className="btn-sm-outline !px-2 !py-1 text-[11px]" onClick={() => setRevealed((v) => !v)}>
                  {revealed ? "隐藏" : "显示"}
                </button>
                <CopyButton
                  label="复制"
                  copied={copied === "dbg"}
                  onClick={() => void copy("dbg", token.access_token)}
                  className="!px-2 !py-1 text-[11px]"
                />
              </div>
            </div>
            <p className="text-ink-muted">过期：{new Date(token.expires_at).toLocaleString()}</p>
            <p className="text-ink-faint">{token.warning}</p>
          </div>
        )}
      </div>
    </details>
  );
}
