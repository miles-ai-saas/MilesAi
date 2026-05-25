"use client";

/** 创建/编辑弹窗：HTTP·SSE 填 URL；STDIO 填 command 与 args（经 MCP Runner 沙箱同步/调用）。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { McpTransportTab } from "@/lib/mcp-labels";
import { mcpTransportLabel, normalizeMcpTransport } from "@/lib/mcp-labels";
import type { McpService } from "@/lib/types";

export type McpDialogMode = "create" | "edit";

type Props = {
  open: boolean;
  mode: McpDialogMode;
  transport: Exclude<McpTransportTab, "">;
  editing: McpService | null;
  name: string;
  description: string;
  endpointUrl: string;
  stdioCommand: string;
  stdioArgs: string;
  busy: boolean;
  onClose: () => void;
  onSubmit: () => void;
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
  name,
  description,
  endpointUrl,
  stdioCommand,
  stdioArgs,
  busy,
  onClose,
  onSubmit,
  onNameChange,
  onDescriptionChange,
  onEndpointUrlChange,
  onStdioCommandChange,
  onStdioArgsChange,
}: Props) {
  const t = editing ? normalizeMcpTransport(editing.transport) : transport;
  const isStdio = t === "stdio";

  return (
    <ResourceDialog
      open={open}
      title={
        mode === "create"
          ? `添加 ${mcpTransportLabel(t)} MCP 服务`
          : `编辑 MCP 服务`
      }
      size="lg"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onSubmit} disabled={busy}>
            {busy ? "保存中…" : mode === "create" ? "创建" : "保存"}
          </button>
        </>
      }
    >
      <label className="block text-xs text-ink-muted">
        名称
        <input
          className="input-field mt-1 w-full"
          placeholder="例如 lbs-amap-http-mcp"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
        />
      </label>
      <label className="block text-xs text-ink-muted">
        描述（可选）
        <input
          className="input-field mt-1 w-full"
          placeholder="例如 高德地图 HTTP MCP"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
        />
      </label>
      {isStdio ? (
        <>
          <label className="block text-xs text-ink-muted">
            启动命令
            <input
              className="input-field mt-1 w-full font-mono text-sm"
              placeholder="npx"
              value={stdioCommand}
              onChange={(e) => onStdioCommandChange(e.target.value)}
            />
          </label>
          <label className="block text-xs text-ink-muted">
            参数（每行一个）
            <textarea
              className="input-field mt-1 min-h-[72px] w-full font-mono text-sm"
              placeholder={"-y\n@amap/mcp-server"}
              value={stdioArgs}
              onChange={(e) => onStdioArgsChange(e.target.value)}
            />
          </label>
          <p className="text-xs text-amber-700">
            STDIO 经平台 MCP Runner 沙箱执行；需管理员启用 Runner。预装 MCP 可用
            <code className="text-xs">mcp-server-everything</code>，npx 拉包需配置 network_mode=allow。
          </p>
        </>
      ) : (
        <label className="block text-xs text-ink-muted">
          端点 URL
          {t === "sse" && (
            <span className="mt-1 block font-normal text-ink-faint">
              SSE 请填写长连接 GET 地址（如 /sse）；平台将自动接收 endpoint 事件并向消息 URL POST。
            </span>
          )}
          <input
            className="input-field mt-1 w-full font-mono text-sm"
            placeholder={
              t === "http"
                ? "https://example.com/mcp"
                : "http://127.0.0.1:3001/sse"
            }
            value={endpointUrl}
            onChange={(e) => onEndpointUrlChange(e.target.value)}
          />
        </label>
      )}
    </ResourceDialog>
  );
}
