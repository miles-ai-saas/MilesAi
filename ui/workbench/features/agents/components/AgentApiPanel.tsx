"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { AgentDebugToken } from "@/lib/types";

type Props = { agentId: string };

type CodeTab = "curl" | "python";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function maskToken(token: string): string {
  if (token.length <= 12) return "••••••••";
  return `${token.slice(0, 8)}…${token.slice(-4)}`;
}

export function AgentApiPanel({ agentId }: Props) {
  const chatUrl = `${API_BASE}/agents/${agentId}/chat`;
  const [token, setToken] = useState<AgentDebugToken | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [codeTab, setCodeTab] = useState<CodeTab>("curl");
  const [copied, setCopied] = useState<string | null>(null);

  const bearer = token?.access_token ?? "YOUR_TOKEN";
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

  const curlSnippet = `curl -sS -X POST '${chatUrl}' \\
  -H 'Authorization: Bearer ${bearer}' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify({ query: "你好" })}'`;

  const pythonSnippet = `import requests

url = "${chatUrl}"
headers = {
    "Authorization": "Bearer ${bearer}",
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

  const copy = async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } catch {
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
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 space-y-4 overflow-auto px-6 py-4">
        <p className="rounded-lg border border-line bg-surface-subtle px-3 py-2 text-xs text-ink-muted">
          一期提供对接调试：使用短期调试 Token 调用下方 HTTP 对话接口。正式 API Key 与独立入口后续提供。
        </p>

        <section className="space-y-2">
          <h3 className="text-sm font-medium text-ink">调用信息</h3>
          <div className="rounded-xl border border-line bg-surface p-3 text-xs">
            <div className="flex items-start justify-between gap-2">
              <code className="break-all text-ink">POST {chatUrl}</code>
              <button type="button" className="shrink-0 text-brand hover:underline" onClick={() => copy("url", chatUrl)}>
                {copied === "url" ? "已复制" : "复制"}
              </button>
            </div>
            <p className="mt-2 text-ink-muted">Header: Authorization: Bearer &lt;token&gt;</p>
            <p className="text-ink-muted">Header: Content-Type: application/json</p>
          </div>
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">调试 Token</h3>
            <button
              type="button"
              disabled={busy}
              onClick={onMint}
              className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {busy ? "生成中…" : token ? "重新生成" : "生成调试 Token"}
            </button>
          </div>
          {token && (
            <div className="space-y-2 rounded-xl border border-line bg-surface p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <code className="break-all text-ink">{revealed ? token.access_token : maskToken(token.access_token)}</code>
                <div className="flex shrink-0 gap-2">
                  <button type="button" className="text-brand hover:underline" onClick={() => setRevealed((v) => !v)}>
                    {revealed ? "隐藏" : "显示"}
                  </button>
                  <button type="button" className="text-brand hover:underline" onClick={() => copy("token", token.access_token)}>
                    {copied === "token" ? "已复制" : "复制"}
                  </button>
                </div>
              </div>
              <p className="text-ink-muted">过期：{new Date(token.expires_at).toLocaleString()}</p>
              <p className="text-ink-faint">{token.warning}</p>
              <p className="text-ink-faint">重新生成不会吊销旧 Token，旧 Token 仍可用至过期。</p>
            </div>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink">请求示例</h3>
            <button type="button" className="text-xs text-brand hover:underline" onClick={() => copy("req", requestJson)}>
              {copied === "req" ? "已复制" : "复制"}
            </button>
          </div>
          <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 text-[11px] text-ink">{requestJson}</pre>
          <p className="text-[11px] text-ink-faint">进阶字段（工具确认、生图预设等）见 ChatRequest / OpenAPI。</p>
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">代码示例</h3>
            <div className="inline-flex rounded-lg border border-line p-0.5">
              {(["curl", "python"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setCodeTab(id)}
                  className={`rounded-md px-2.5 py-1 text-xs ${codeTab === id ? "bg-brand-light text-brand" : "text-ink-muted"}`}
                >
                  {id === "curl" ? "curl" : "Python"}
                </button>
              ))}
            </div>
          </div>
          <div className="relative">
            <button
              type="button"
              className="absolute right-2 top-2 text-xs text-brand hover:underline"
              onClick={() => copy("code", codeTab === "curl" ? curlSnippet : pythonSnippet)}
            >
              {copied === "code" ? "已复制" : "复制"}
            </button>
            <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 pr-16 text-[11px] text-ink">
              {codeTab === "curl" ? curlSnippet : pythonSnippet}
            </pre>
          </div>
        </section>

        <section className="space-y-2 pb-4">
          <h3 className="text-sm font-medium text-ink">响应示例</h3>
          <pre className="overflow-x-auto rounded-xl border border-line bg-surface-subtle p-3 text-[11px] text-ink">{responseExample}</pre>
        </section>
      </div>
    </div>
  );
}
