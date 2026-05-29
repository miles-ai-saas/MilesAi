"use client";

import { CodeEditor } from "@/components/editor/CodeEditor";
import { TagPicker } from "@/components/tag/TagPicker";
import type { ToolDialogMode } from "@/features/tools/components/ToolCreateDialog";

type BasicFieldsProps = {
  mode: ToolDialogMode;
  slug: string;
  name: string;
  description: string;
  tagIds: string[];
  version: string;
  requireConfirmation: boolean;
  onSlugChange: (v: string) => void;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onTagIdsChange: (v: string[]) => void;
  onVersionChange: (v: string) => void;
  onRequireConfirmationChange: (v: boolean) => void;
};

export function ToolCreateDialogBasicFields({
  mode,
  slug,
  name,
  description,
  tagIds,
  version,
  requireConfirmation,
  onSlugChange,
  onNameChange,
  onDescriptionChange,
  onTagIdsChange,
  onVersionChange,
  onRequireConfirmationChange,
}: BasicFieldsProps) {
  return (
    <>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">名称 *</span>
        <input className="input-field w-full" placeholder="例如：天气查询" value={name} onChange={(e) => onNameChange(e.target.value)} />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">编号 *</span>
        <input
          className="input-field w-full font-mono"
          placeholder="weather_query"
          value={slug}
          disabled={mode === "edit"}
          onChange={(e) => onSlugChange(e.target.value.toLowerCase())}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">描述</span>
        <textarea
          className="input-field min-h-[72px] w-full resize-y"
          placeholder="供 LLM 理解工具用途"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">标签</span>
        <TagPicker value={tagIds} onChange={onTagIdsChange} />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">版本</span>
          <input className="input-field w-full" value={version} onChange={(e) => onVersionChange(e.target.value)} />
        </label>
        <label className="flex min-h-[42px] items-center justify-between rounded-lg border border-line-soft bg-surface px-3 text-xs">
          <span className="text-ink-muted">执行前需确认</span>
          <input type="checkbox" checked={requireConfirmation} onChange={(e) => onRequireConfirmationChange(e.target.checked)} />
        </label>
      </div>
    </>
  );
}

type HttpFieldsProps = {
  url: string;
  method: string;
  headersJson: string;
  bodyMode: "json" | "none";
  timeoutSec: number;
  onUrlChange: (v: string) => void;
  onMethodChange: (v: string) => void;
  onHeadersJsonChange: (v: string) => void;
  onBodyModeChange: (v: "json" | "none") => void;
  onTimeoutSecChange: (v: number) => void;
};

export function ToolCreateDialogHttpFields({
  url,
  method,
  headersJson,
  bodyMode,
  timeoutSec,
  onUrlChange,
  onMethodChange,
  onHeadersJsonChange,
  onBodyModeChange,
  onTimeoutSecChange,
}: HttpFieldsProps) {
  return (
    <>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">URL *</span>
        <input
          className="input-field w-full font-mono text-sm"
          placeholder="https://api.example.com/weather?city={{city}}"
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
        />
      </label>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">方法</span>
          <select className="input-field w-full" value={method} onChange={(e) => onMethodChange(e.target.value)}>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="PATCH">PATCH</option>
          </select>
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">Body</span>
          <select className="input-field w-full" value={bodyMode} onChange={(e) => onBodyModeChange(e.target.value as "json" | "none")}>
            <option value="json">JSON</option>
            <option value="none">无 Body</option>
          </select>
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-ink-muted">超时（秒）</span>
          <input
            type="number"
            min={1}
            max={120}
            className="input-field w-full"
            value={timeoutSec}
            onChange={(e) => onTimeoutSecChange(Number(e.target.value) || 15)}
          />
        </label>
      </div>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">Headers（JSON）</span>
        <textarea
          className="input-field min-h-[88px] w-full resize-y font-mono text-xs"
          placeholder='{"Authorization": "Bearer xxx"}'
          value={headersJson}
          onChange={(e) => onHeadersJsonChange(e.target.value)}
        />
      </label>
    </>
  );
}

type ScriptFieldsProps = {
  scriptSource: string;
  timeoutSec: number;
  onScriptSourceChange: (v: string) => void;
  onTimeoutSecChange: (v: number) => void;
};

export function ToolCreateDialogScriptFields({ scriptSource, timeoutSec, onScriptSourceChange, onTimeoutSecChange }: ScriptFieldsProps) {
  return (
    <>
      <label className="block min-h-0 flex-1 text-xs">
        <span className="mb-1 block text-ink-muted">源码 *</span>
        <CodeEditor
          language="python"
          value={scriptSource}
          onChange={onScriptSourceChange}
          height="min(420px, calc(100vh - 22rem))"
          aria-label="Python 脚本源码"
        />
      </label>
      <label className="block max-w-xs text-xs">
        <span className="mb-1 block text-ink-muted">超时（秒）</span>
        <input
          type="number"
          min={1}
          max={120}
          className="input-field w-full"
          value={timeoutSec}
          onChange={(e) => onTimeoutSecChange(Number(e.target.value) || 30)}
        />
      </label>
    </>
  );
}
