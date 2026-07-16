"use client";

import { useState } from "react";
import { copyText } from "@/features/agents/lib/agent-trace";
import { AgentApiKeyCard } from "@/features/agents/components/AgentApiKeyCard";
import { AgentApiCodeExamples } from "@/features/agents/components/AgentApiCodeExamples";
import { AgentApiDebugToken } from "@/features/agents/components/AgentApiDebugToken";

type Props = { agentId: string };

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function CopyButton({ label, copied, onClick, className = "" }: { label: string; copied: boolean; onClick: () => void; className?: string }) {
  return (
    <button type="button" className={`btn-sm-outline shrink-0 ${className}`} onClick={onClick}>
      {copied ? "已复制" : label}
    </button>
  );
}

export function AgentApiPanel({ agentId }: Props) {
  const openUrl = `${API_BASE}/open/agents/${agentId}/chat`;
  const [error, setError] = useState<string | null>(null);
  const [demoKey, setDemoKey] = useState("YOUR_API_KEY");
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-soft bg-surface-subtle/50 px-6 py-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-brand-light px-2 py-0.5 font-mono text-[11px] font-semibold text-brand">
              POST
            </span>
            <span className="text-sm font-medium text-ink">正式 API 对接</span>
            <span className="rounded border border-line px-1.5 py-px text-[10px] text-ink-faint">X-API-Key</span>
          </div>
          <p className="text-xs text-ink-muted">创建并保管 API Key，调用开放入口完成生产对接；调试 Token 仅建议本地试通。</p>
        </div>
      </div>

      {error && (
        <p className="shrink-0 border-b border-line-soft bg-red-50/90 px-6 py-2 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-5xl gap-4 px-6 py-4 lg:grid-cols-5 lg:items-start">
          <div className="flex flex-col gap-4 lg:col-span-2 lg:sticky lg:top-0">
            <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card">
              <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-4 py-2.5">
                <h3 className="text-sm font-medium text-ink">调用信息</h3>
                <CopyButton label="复制 URL" copied={copied === "url"} onClick={() => void copy("url", openUrl)} />
              </div>
              <div className="p-4">
                <dl className="space-y-3">
                  <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]">
                    <dt className="pt-0.5 text-ink-muted">Method</dt>
                    <dd className="min-w-0 text-ink">
                      <span className="inline-flex rounded-md bg-brand-light px-1.5 py-0.5 font-mono text-[11px] font-semibold text-brand">POST</span>
                    </dd>
                  </div>
                  <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]">
                    <dt className="pt-0.5 text-ink-muted">URL</dt>
                    <dd className="min-w-0 text-ink">
                      <code className="block break-all rounded-md bg-surface-subtle px-2 py-1.5 font-mono text-[11px] leading-snug">{openUrl}</code>
                    </dd>
                  </div>
                  <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]">
                    <dt className="pt-0.5 text-ink-muted">Auth</dt>
                    <dd className="min-w-0 text-ink">
                      <code className="font-mono text-[11px]">X-API-Key: mil_…</code>
                    </dd>
                  </div>
                  <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]">
                    <dt className="pt-0.5 text-ink-muted">兼容</dt>
                    <dd className="min-w-0 text-ink">
                      <span className="text-[11px] text-ink-muted">亦可对 `/agents/{"{id}"}/chat` 使用同一 X-API-Key</span>
                    </dd>
                  </div>
                </dl>
              </div>
            </section>
            <AgentApiKeyCard agentId={agentId} onDemoKeyChange={setDemoKey} setError={setError} />
          </div>

          <div className="flex flex-col gap-4 lg:col-span-3">
            <AgentApiCodeExamples agentId={agentId} demoKey={demoKey} setError={setError} />
            <AgentApiDebugToken agentId={agentId} setError={setError} />
          </div>
        </div>
      </div>
    </div>
  );
}
