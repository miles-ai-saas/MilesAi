"use client";

import { MCP_ENDPOINT_PLACEHOLDER, MCP_TRANSPORT_HINTS, McpDialogSection } from "@/features/mcp/components/mcp-dialog-shared";
import type { McpTransportTab } from "@/features/mcp/lib/mcp-labels";

type Props = {
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
};

export function McpServiceDialogForm({
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
}: Props) {
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
