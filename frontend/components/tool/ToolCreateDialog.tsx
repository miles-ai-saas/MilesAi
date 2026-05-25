"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ToolParameterEditor } from "@/components/tool/ToolParameterEditor";
import { TagPicker } from "@/components/tag/TagPicker";
import type { CustomTool, ToolParameterSpec } from "@/lib/types";
import type { SysCategory } from "@/lib/types";

export type ToolDialogMode = "create" | "edit";

type Props = {
  open: boolean;
  mode: ToolDialogMode;
  editing: CustomTool | null;
  categories: SysCategory[];
  slug: string;
  name: string;
  description: string;
  categoryId: string;
  tagIds: string[];
  version: string;
  requireConfirmation: boolean;
  parameters: ToolParameterSpec[];
  url: string;
  method: string;
  headersJson: string;
  busy: boolean;
  onClose: () => void;
  onSubmit: () => void;
  onSlugChange: (v: string) => void;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onCategoryIdChange: (v: string) => void;
  onTagIdsChange: (v: string[]) => void;
  onVersionChange: (v: string) => void;
  onRequireConfirmationChange: (v: boolean) => void;
  onParametersChange: (v: ToolParameterSpec[]) => void;
  onUrlChange: (v: string) => void;
  onMethodChange: (v: string) => void;
  onHeadersJsonChange: (v: string) => void;
};

export function ToolCreateDialog({
  open,
  mode,
  editing,
  categories,
  slug,
  name,
  description,
  categoryId,
  tagIds,
  version,
  requireConfirmation,
  parameters,
  url,
  method,
  headersJson,
  busy,
  onClose,
  onSubmit,
  onSlugChange,
  onNameChange,
  onDescriptionChange,
  onCategoryIdChange,
  onTagIdsChange,
  onVersionChange,
  onRequireConfirmationChange,
  onParametersChange,
  onUrlChange,
  onMethodChange,
  onHeadersJsonChange,
}: Props) {
  return (
    <ResourceDialog
      open={open}
      title={mode === "create" ? "新增工具" : `编辑 · ${editing?.name ?? ""}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={onSubmit}>
            {busy ? "保存中…" : mode === "create" ? "创建" : "保存"}
          </button>
        </>
      }
    >
      <div className="mb-4 rounded-lg border border-brand/20 bg-brand-light/40 px-3 py-2 text-xs text-brand">
        当前支持 HTTP 工具。脚本工具（在线代码）将在后续版本提供；异步/流式工具请通过 MCP 接入。
      </div>

      <div className="space-y-4">
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">分类</span>
          <select
            className="input-field w-full"
            value={categoryId}
            onChange={(e) => onCategoryIdChange(e.target.value)}
          >
            <option value="">未分类</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">标签</span>
          <TagPicker value={tagIds} onChange={onTagIdsChange} />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">名称 *</span>
          <input
            className="input-field w-full"
            placeholder="请输入工具名称"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">编号 *</span>
          <input
            className="input-field w-full font-mono"
            placeholder="小写字母+下划线，如 weather_query"
            value={slug}
            disabled={mode === "edit"}
            onChange={(e) => onSlugChange(e.target.value.toLowerCase())}
          />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">描述</span>
          <textarea
            className="input-field min-h-[72px] w-full"
            placeholder="请输入工具描述"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
          />
        </label>

        <label className="flex items-center justify-between text-xs">
          <span className="text-ink-muted">是否需要确认</span>
          <input
            type="checkbox"
            checked={requireConfirmation}
            onChange={(e) => onRequireConfirmationChange(e.target.checked)}
          />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">版本号</span>
          <input
            className="input-field w-full"
            value={version}
            onChange={(e) => onVersionChange(e.target.value)}
          />
        </label>

        <div>
          <span className="mb-2 block text-xs text-ink-muted">输入参数</span>
          <ToolParameterEditor value={parameters} onChange={onParametersChange} />
        </div>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">URL *</span>
          <input
            className="input-field w-full font-mono text-sm"
            placeholder="https://api.example.com/endpoint?city={{city}}"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
          />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">HTTP 方法</span>
          <select className="input-field w-full" value={method} onChange={(e) => onMethodChange(e.target.value)}>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="PATCH">PATCH</option>
          </select>
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">Headers（JSON，可选）</span>
          <textarea
            className="input-field min-h-[64px] w-full font-mono text-xs"
            placeholder='{"Authorization": "Bearer xxx"}'
            value={headersJson}
            onChange={(e) => onHeadersJsonChange(e.target.value)}
          />
        </label>
      </div>
    </ResourceDialog>
  );
}
