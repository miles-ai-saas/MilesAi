"use client";

import { useMemo, useState } from "react";
import { copyText } from "@/features/agents/lib/agent-trace";

type ExampleTab = "request" | "response" | "curl" | "python";

function CopyButton({ label, copied, onClick, className = "" }: { label: string; copied: boolean; onClick: () => void; className?: string }) {
  return (
    <button type="button" className={`btn-sm-outline shrink-0 ${className}`} onClick={onClick}>
      {copied ? "已复制" : label}
    </button>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="max-h-[22rem] overflow-auto rounded-lg border border-line-soft bg-surface-subtle/80 p-3 font-mono text-[11px] leading-relaxed text-ink">
      {children}
    </pre>
  );
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

type Props = {
  agentId: string;
  demoKey: string;
  setError: (err: string | null) => void;
};

export function AgentApiCodeExamples({ agentId, demoKey, setError }: Props) {
  const openUrl = `${API_BASE}/open/agents/${agentId}/chat`;
  const [exampleTab, setExampleTab] = useState<ExampleTab>("curl");
  const [copied, setCopied] = useState<string | null>(null);

  const requestJson = useMemo(
    () => JSON.stringify({ query: "你好", conversation_id: null, media: [], inputs: {} }, null, 2),
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
    { code: 0, message: "ok", data: { answer: "你好！有什么可以帮你的？", sources: [], steps: [], artifacts: [], pending_tool: null, generative_jobs: [] } },
    null,
    2,
  );

  const exampleBody =
    exampleTab === "request" ? requestJson
    : exampleTab === "response" ? responseExample
    : exampleTab === "curl" ? curlSnippet
    : pythonSnippet;

  const exampleTabs: { id: ExampleTab; label: string }[] = [
    { id: "curl", label: "curl" },
    { id: "python", label: "Python" },
    { id: "request", label: "请求体" },
    { id: "response", label: "响应" },
  ];

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
    <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line-soft px-4 py-2.5">
        <h3 className="text-sm font-medium text-ink">示例代码</h3>
        <CopyButton label="复制当前" copied={copied === "example"} onClick={() => void copy("example", exampleBody)} />
      </div>
      <div className="p-4">
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
      </div>
    </section>
  );
}
