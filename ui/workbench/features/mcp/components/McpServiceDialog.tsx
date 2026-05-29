"use client";

/** MCP 创建/编辑（链路 §11）：HTTP/SSE/STDIO 分节表单 → api。 */

import type { ReactNode } from "react";
import { KbPageAlert } from "@/features/kb";
import type { McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { mcpTransportLabel, normalizeMcpTransport } from "@/features/mcp/lib/mcp-labels";
import { MCP_ENDPOINT_PLACEHOLDER } from "@/features/mcp/hooks/use-mcp-form";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { McpMeta, McpService } from "@/lib/types";

export type McpDialogMode = "create" | "edit";

export function McpDialogSection({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface-muted/30 p-4">
      <div className="mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
        {hint ? <p className="mt-1 text-xs leading-relaxed text-ink-faint">{hint}</p> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function McpDetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-3 sm:grid-cols-[7rem_1fr]">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-sm text-ink">{children}</dd>
    </div>
  );
}

const MCP_TRANSPORT_HINTS: Record<Exclude<McpTransportTab, "">, string> = {
  http: "填写 Streamable HTTP 端点（如 https://host/mcp），平台优先 JSON，必要时回退 SSE。",
  sse: "填写 Legacy SSE 长连接 GET 地址（如 http://host/sse）；将接收 endpoint 事件并向消息 URL POST。",
  stdio: "经 MCP Runner 沙箱启动子进程；需管理员启用 Runner。npx 拉包需 network_mode=allow。",
};

export function McpTransportBadge({ transport, mcpMeta }: { transport: Exclude<McpTransportTab, "">; mcpMeta?: McpMeta | null }) {
  return (
    <span className="inline-flex rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-[10px] font-medium text-brand">
      {mcpTransportLabel(transport, mcpMeta)}
    </span>
  );
}

function mcpFormCanSubmit(opts: {
  name: string;
  transport: Exclude<McpTransportTab, "">;
  endpointUrl: string;
  stdioCommand: string;
  busy: boolean;
}): boolean {
  if (opts.busy || !opts.name.trim()) return false;
  if (opts.transport === "stdio") return Boolean(opts.stdioCommand.trim());
  return Boolean(opts.endpointUrl.trim());
}

type TransportTab = {
  key: Exclude<McpTransportTab, "">;
  label: string;
  hint: string;
};

function McpServiceDialogTransport({
  transport,
  transportLocked,
  mcpMeta,
  onTransportChange,
}: {
  transport: Exclude<McpTransportTab, "">;
  transportLocked: boolean;
  mcpMeta?: McpMeta | null;
  onTransportChange?: (t: Exclude<McpTransportTab, "">) => void;
}) {
  const tabs: TransportTab[] = (["http", "sse", "stdio"] as const).map((key) => ({
    key,
    label: mcpTransportLabel(key, mcpMeta),
    hint: MCP_TRANSPORT_HINTS[key],
  }));

  if (transportLocked) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-muted">传输类型</span>
        <McpTransportBadge transport={transport} mcpMeta={mcpMeta} />
      </div>
    );
  }

  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
      {tabs.map((tab) => {
        const active = transport === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            title={tab.hint}
            onClick={() => onTransportChange?.(tab.key)}
            className={`rounded-lg px-4 py-2 text-left transition ${
              active ? "bg-brand-light text-brand shadow-sm ring-1 ring-brand/20" : "text-ink-muted hover:bg-surface-muted hover:text-ink"
            }`}
          >
            <span className="text-sm font-medium">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function McpServiceDialogForm({
  transport,
  name,
  description,
  endpointUrl,
  stdioCommand,
  stdioArgs,
  onNameChange,
  onDescriptionChange,
  onEndpointUrlChange,
  onStdioCommandChange,
  onStdioArgsChange,
}: {
  transport: Exclude<McpTransportTab, "">;
  name: string;
  description: string;
  endpointUrl: string;
  stdioCommand: string;
  stdioArgs: string;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onEndpointUrlChange: (v: string) => void;
  onStdioCommandChange: (v: string) => void;
  onStdioArgsChange: (v: string) => void;
}) {
  const isStdio = transport === "stdio";

  return (
    <>
      <McpDialogSection title="基本信息" hint="名称在租户内用于展示与绑定智能体">
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">名称 *</span>
          <input className="input-field w-full" placeholder="例如 lbs-amap-http-mcp" value={name} onChange={(e) => onNameChange(e.target.value)} />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">描述</span>
          <textarea
            className="input-field min-h-[72px] w-full resize-y"
            placeholder="例如 高德地图 HTTP MCP，供智能体选用"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
          />
        </label>
      </McpDialogSection>

      <McpDialogSection title={isStdio ? "STDIO 启动" : "端点连接"} hint={MCP_TRANSPORT_HINTS[transport]}>
        {isStdio ? (
          <>
            <label className="block text-xs">
              <span className="mb-1 block text-ink-muted">启动命令 *</span>
              <input className="input-field w-full font-mono text-sm" placeholder="npx" value={stdioCommand} onChange={(e) => onStdioCommandChange(e.target.value)} />
            </label>
            <label className="block text-xs">
              <span className="mb-1 block text-ink-muted">参数（每行一个）</span>
              <textarea
                className="input-field min-h-[88px] w-full resize-y font-mono text-sm"
                placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/path/to/dir"}
                value={stdioArgs}
                onChange={(e) => onStdioArgsChange(e.target.value)}
              />
            </label>
            <p className="text-xs text-amber-800">
              预装示例可用 <code className="font-mono text-[11px]">mcp-server-everything</code>
              ；npx 在线拉包需 Runner 配置 <code className="font-mono text-[11px]">network_mode=allow</code>。
            </p>
          </>
        ) : (
          <label className="block text-xs">
            <span className="mb-1 block text-ink-muted">端点 URL *</span>
            <input
              className="input-field w-full font-mono text-sm"
              placeholder={MCP_ENDPOINT_PLACEHOLDER[transport]}
              value={endpointUrl}
              onChange={(e) => onEndpointUrlChange(e.target.value)}
            />
            {transport === "sse" && (
              <span className="mt-2 block text-xs leading-relaxed text-ink-faint">
                SSE 请填写长连接 GET 地址；平台将自动处理 endpoint 事件与消息 URL POST。
              </span>
            )}
          </label>
        )}
      </McpDialogSection>
    </>
  );
}

type Props = {
  open: boolean;
  mode: McpDialogMode;
  transport: Exclude<McpTransportTab, "">;
  editing: McpService | null;
  mcpMeta?: McpMeta | null;
  name: string;
  description: string;
  endpointUrl: string;
  stdioCommand: string;
  stdioArgs: string;
  busy: boolean;
  saveError?: string;
  onClose: () => void;
  onSubmit: () => void;
  onDismissError?: () => void;
  onTransportChange?: (t: Exclude<McpTransportTab, "">) => void;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onEndpointUrlChange: (v: string) => void;
  onStdioCommandChange: (v: string) => void;
  onStdioArgsChange: (v: string) => void;
};

export function McpServiceDialog({
  open,
  mode,
  transport,
  editing,
  mcpMeta,
  name,
  description,
  endpointUrl,
  stdioCommand,
  stdioArgs,
  busy,
  saveError,
  onClose,
  onSubmit,
  onDismissError,
  onTransportChange,
  onNameChange,
  onDescriptionChange,
  onEndpointUrlChange,
  onStdioCommandChange,
  onStdioArgsChange,
}: Props) {
  const t = editing ? normalizeMcpTransport(editing.transport) : transport;
  const transportLocked = mode === "edit";
  const canSubmit = mcpFormCanSubmit({
    name,
    transport: t,
    endpointUrl,
    stdioCommand,
    busy,
  });

  return (
    <ResourceDialog
      open={open}
      size="sheet"
      contentMaxWidth="max-w-3xl"
      title={mode === "create" ? "添加 MCP 服务" : `编辑 · ${editing?.name ?? ""}`}
      description={
        mode === "create" ? "选择传输类型并填写连接信息；创建后请在详情中「同步工具」拉取 tools/list。" : "修改名称、描述或连接配置；传输类型创建后不可更改。"
      }
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onSubmit} disabled={!canSubmit}>
            {busy ? "保存中…" : mode === "create" ? "创建" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        {saveError ? <KbPageAlert tone="error" message={saveError} onDismiss={onDismissError} /> : null}

        <McpServiceDialogTransport transport={t} transportLocked={transportLocked} mcpMeta={mcpMeta} onTransportChange={onTransportChange} />

        <McpServiceDialogForm
          transport={t}
          name={name}
          description={description}
          endpointUrl={endpointUrl}
          stdioCommand={stdioCommand}
          stdioArgs={stdioArgs}
          onNameChange={onNameChange}
          onDescriptionChange={onDescriptionChange}
          onEndpointUrlChange={onEndpointUrlChange}
          onStdioCommandChange={onStdioCommandChange}
          onStdioArgsChange={onStdioArgsChange}
        />
      </div>
    </ResourceDialog>
  );
}
