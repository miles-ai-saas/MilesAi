"use client";

/** MCP 创建/编辑（链路 §11）：HTTP/SSE/STDIO 分节表单 → api。 */

import { KbPageAlert } from "@/features/kb";
import { mcpFormCanSubmit } from "@/features/mcp/components/mcp-dialog-shared";
import { McpServiceDialogForm } from "@/features/mcp/components/McpServiceDialogForm";
import { McpServiceDialogTransport } from "@/features/mcp/components/McpServiceDialogTransport";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { McpDialogMode } from "@/features/mcp/components/McpServiceDialog.types";
import type { McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { normalizeMcpTransport } from "@/features/mcp/lib/mcp-labels";
import type { McpMeta, McpService } from "@/lib/types";

export type { McpDialogMode };

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
