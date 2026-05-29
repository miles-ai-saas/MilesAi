"use client";

/** 自定义工具创建/编辑（链路 §3 + §4 tools meta）。 */

import { KbPageAlert } from "@/features/kb";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ToolCreateDialogEntityForm } from "@/features/tools/components/ToolCreateDialogEntityForm";
import type { ToolCreateDialogKindTab } from "@/features/tools/lib/tool-create-dialog-shared";
import type { ToolDialogMode } from "@/features/tools/lib/tool-create-dialog-shared";
import type { ToolKindTab } from "@/features/tools/lib/tool-labels";
import type { CustomTool, ToolParameterSpec } from "@/lib/types";

function ToolCreateDialogKindSelector({
  kindTabs,
  toolKind,
  kindLocked,
  onToolKindChange,
}: {
  kindTabs: ToolCreateDialogKindTab[];
  toolKind: ToolKindTab;
  kindLocked: boolean;
  onToolKindChange: (v: ToolKindTab) => void;
}) {
  if (kindLocked) return null;

  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
      {kindTabs.map((tab) => {
        const active = toolKind === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            disabled={!tab.available}
            title={tab.hint}
            onClick={() => tab.available && onToolKindChange(tab.key)}
            className={`rounded-lg px-4 py-2 text-left transition ${
              active
                ? "bg-brand-light text-brand shadow-sm ring-1 ring-brand/20"
                : tab.available
                  ? "text-ink-muted hover:bg-surface-muted hover:text-ink"
                  : "cursor-not-allowed opacity-50"
            }`}
          >
            <span className="text-sm font-medium">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export type { ToolDialogMode } from "@/features/tools/lib/tool-create-dialog-shared";
export { DEFAULT_SCRIPT } from "@/features/tools/lib/tool-create-dialog-shared";

type Props = {
  open: boolean;
  mode: ToolDialogMode;
  kindTabs: ToolCreateDialogKindTab[];
  toolKind: ToolKindTab;
  editing: CustomTool | null;
  slug: string;
  name: string;
  description: string;
  tagIds: string[];
  version: string;
  requireConfirmation: boolean;
  parameters: ToolParameterSpec[];
  url: string;
  method: string;
  headersJson: string;
  bodyMode: "json" | "none";
  timeoutSec: number;
  scriptSource: string;
  busy: boolean;
  saveError?: string;
  onClose: () => void;
  onDismissError?: () => void;
  onSubmit: () => void;
  onToolKindChange: (v: ToolKindTab) => void;
  onSlugChange: (v: string) => void;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onTagIdsChange: (v: string[]) => void;
  onVersionChange: (v: string) => void;
  onRequireConfirmationChange: (v: boolean) => void;
  onParametersChange: (v: ToolParameterSpec[]) => void;
  onUrlChange: (v: string) => void;
  onMethodChange: (v: string) => void;
  onHeadersJsonChange: (v: string) => void;
  onBodyModeChange: (v: "json" | "none") => void;
  onTimeoutSecChange: (v: number) => void;
  onScriptSourceChange: (v: string) => void;
};

export function ToolCreateDialog({
  open,
  mode,
  kindTabs,
  toolKind,
  editing,
  busy,
  saveError = "",
  onClose,
  onDismissError,
  onSubmit,
  onToolKindChange,
  ...entityProps
}: Props) {
  const isHttp = toolKind === "http";
  const canSubmit =
    Boolean(entityProps.name.trim() && entityProps.slug.trim()) &&
    !busy &&
    (isHttp ? Boolean(entityProps.url.trim()) : Boolean(entityProps.scriptSource.trim()));
  const kindLocked = mode === "edit";

  return (
    <ResourceDialog
      open={open}
      size="sheet"
      contentMaxWidth="max-w-6xl"
      title={mode === "create" ? "新增工具" : `编辑 · ${editing?.name ?? ""}`}
      description={mode === "create" ? "左侧填写元数据，右侧配置参数与 HTTP / 脚本执行方式。" : undefined}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={!canSubmit} onClick={onSubmit}>
            {busy ? "保存中…" : mode === "create" ? "创建" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        {saveError ? <KbPageAlert tone="error" message={saveError} onDismiss={onDismissError} /> : null}
        <ToolCreateDialogKindSelector kindTabs={kindTabs} toolKind={toolKind} kindLocked={kindLocked} onToolKindChange={onToolKindChange} />
        <ToolCreateDialogEntityForm mode={mode} toolKind={toolKind} {...entityProps} />
      </div>
    </ResourceDialog>
  );
}
