"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { AgentApiKey, AgentApiKeyCreated, AgentDebugToken } from "@/lib/types";

type Props = { agentId: string };

type ExampleTab = "request" | "response" | "curl" | "python";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function maskToken(token: string): string {
  if (token.length <= 16) return "••••••••••••";
  return `${token.slice(0, 10)}…${token.slice(-6)}`;
}

function CopyButton({
  label,
  copied,
  onClick,
  className = "",
}: {
  label: string;
  copied: boolean;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button type="button" className={`btn-sm-outline shrink-0 ${className}`} onClick={onClick}>
      {copied ? "已复制" : label}
    </button>
  );
}

function PanelCard({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card ${className}`}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-4 py-2.5">
        <h3 className="text-sm font-medium text-ink">{title}</h3>
        {action}
      </div>
      <div className="min-h-0 flex-1 p-4">{children}</div>
    </section>
  );
}

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]">
      <dt className="pt-0.5 text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="max-h-[22rem] overflow-auto rounded-lg border border-line-soft bg-surface-subtle/80 p-3 font-mono text-[11px] leading-relaxed text-ink">
      {children}
    </pre>
  );
}

export function AgentApiPanel({ agentId }: Props) {
  const openUrl = `${API_BASE}/open/agents/${agentId}/chat`;
  const [keys, setKeys] = useState<AgentApiKey[]>([]);
  const [keyName, setKeyName] = useState("生产");
  const [created, setCreated] = useState<AgentApiKeyCreated | null>(null);
  const [keysLoading, setKeysLoading] = useState(false);
  const [token, setToken] = useState<AgentDebugToken | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exampleTab, setExampleTab] = useState<ExampleTab>("curl");
  const [copied, setCopied] = useState<string | null>(null);
  const [demoKey, setDemoKey] = useState("YOUR_API_KEY");

  const requestJson = useMemo(
    () =>
      JSON.stringify(
        {
          query: "你好",
          conversation_id: null,
          media: [],
          inputs: {},
        },
        null,
        2,
      ),
    [],
  );

  const curlSnippet = `curl -sS -X POST '${openUrl}' \\
  -H 'X-API-Key: ${demoKey}' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify({ query: "你好" })}'`;

  const pythonSnippet = `import requests

url = "${openUrl}"
headers = {
    "X-API-Key": "${demoKey}",
    "Content-Type": "application/json",
}
resp = requests.post(url, headers=headers, json={"query": "你好"}, timeout=120)
print(resp.status_code, resp.json())`;

  const responseExample = JSON.stringify(
    {
      code: 0,
      message: "ok",
      data: {
        answer: "你好！有什么可以帮你的？",
        sources: [],
        steps: [],
        artifacts: [],
        pending_tool: null,
        generative_jobs: [],
      },
    },
    null,
    2,
  );

  const exampleBody =
    exampleTab === "request" ? requestJson : exampleTab === "response" ? responseExample : exampleTab === "curl" ? curlSnippet : pythonSnippet;

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
  }, [agentId]);

  useEffect(() => {
    void reloadKeys();
  }, [reloadKeys]);

  const copy = async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setError("复制失败");
    }
  };

  const onCreateKey = async () => {
    if (!keyName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.createAgentApiKey(agentId, keyName.trim());
      setCreated(out);
      setDemoKey(out.secret);
      await reloadKeys();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const onRevoke = async (keyId: string) => {
    if (!window.confirm("确定吊销该密钥？吊销后立即失效且不可恢复明文。")) return;
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

  const onMintDebug = async () => {
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

  const exampleTabs: { id: ExampleTab; label: string }[] = [
    { id: "curl", label: "curl" },
    { id: "python", label: "Python" },
    { id: "request", label: "请求体" },
    { id: "response", label: "响应" },
  ];

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

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-5xl gap-4 px-6 py-4 lg:grid-cols-5 lg:items-start">
          <div className="flex flex-col gap-4 lg:col-span-2 lg:sticky lg:top-0">
            <PanelCard title="调用信息" action={<CopyButton label="复制 URL" copied={copied === "url"} onClick={() => void copy("url", openUrl)} />}>
              <dl className="space-y-3">
                <MetaRow label="Method">
                  <span className="inline-flex rounded-md bg-brand-light px-1.5 py-0.5 font-mono text-[11px] font-semibold text-brand">POST</span>
                </MetaRow>
                <MetaRow label="URL">
                  <code className="block break-all rounded-md bg-surface-subtle px-2 py-1.5 font-mono text-[11px] leading-snug">{openUrl}</code>
                </MetaRow>
                <MetaRow label="Auth">
                  <code className="font-mono text-[11px]">X-API-Key: mil_…</code>
                </MetaRow>
                <MetaRow label="兼容">
                  <span className="text-[11px] text-ink-muted">亦可对 `/agents/{"{id}"}/chat` 使用同一 X-API-Key</span>
                </MetaRow>
              </dl>
            </PanelCard>

            <PanelCard title="API Key">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <input
                    className="input-field min-w-[8rem] flex-1 text-sm"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="密钥名称"
                    maxLength={64}
                  />
                  <button type="button" className="btn-sm-primary shrink-0" disabled={busy || !keyName.trim()} onClick={() => void onCreateKey()}>
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
            </PanelCard>
          </div>

          <div className="flex flex-col gap-4 lg:col-span-3">
            <PanelCard
              title="示例代码"
              action={<CopyButton label="复制当前" copied={copied === "example"} onClick={() => void copy("example", exampleBody)} />}
            >
              <div className="flex min-h-0 flex-col gap-3">
                <div className="inline-flex w-fit flex-wrap rounded-lg border border-line bg-surface-subtle p-0.5" role="tablist" aria-label="示例类型">
                  {exampleTabs.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      aria-selected={exampleTab === tab.id}
                      onClick={() => setExampleTab(tab.id)}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                        exampleTab === tab.id ? "bg-brand-light text-brand shadow-sm" : "text-ink-muted hover:text-ink"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                <CodeBlock>{exampleBody}</CodeBlock>
              </div>
            </PanelCard>

            <details className="rounded-xl border border-line bg-surface shadow-card">
              <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-ink-muted marker:content-none">
                调试 Token（等同登录态，勿用于生产）
              </summary>
              <div className="space-y-3 border-t border-line-soft p-4 text-xs">
                <button type="button" className="btn-sm-outline" disabled={busy} onClick={() => void onMintDebug()}>
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
          </div>
        </div>
      </div>
    </div>
  );
}
