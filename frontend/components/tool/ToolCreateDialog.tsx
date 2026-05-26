"use client";

import { KbPageAlert } from "@/components/kb/KbPageAlert";
import { CodeEditor } from "@/components/editor/CodeEditor";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ToolParameterEditor } from "@/components/tool/ToolParameterEditor";
import { TagPicker } from "@/components/tag/TagPicker";
import type { ToolKindTab } from "@/lib/tool-labels";
import type { CustomTool, ToolParameterSpec } from "@/lib/types";

export type ToolDialogMode = "create" | "edit";

export const DEFAULT_SCRIPT = `def run(params: dict) -> dict:
    """params 对应下方输入参数 schema"""
    # return {"result": params.get("query")}
    raise NotImplementedError("请实现 run(params)")`;

type KindTab = { key: ToolKindTab; label: string; hint: string; available: boolean };

type Props = {
  open: boolean;
  mode: ToolDialogMode;
  kindTabs: KindTab[];
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

function Section({
  title,
  hint,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-line bg-surface-muted/30 p-4 ${className}`}
    >
      <div className="mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
        {hint ? <p className="mt-1 text-xs leading-relaxed text-ink-faint">{hint}</p> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function KindSelector({
  kindTabs,
  toolKind,
  kindLocked,
  onToolKindChange,
}: {
  kindTabs: KindTab[];
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

function BasicFields({
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
}: Pick<
  Props,
  | "mode"
  | "slug"
  | "name"
  | "description"
  | "tagIds"
  | "version"
  | "requireConfirmation"
  | "onSlugChange"
  | "onNameChange"
  | "onDescriptionChange"
  | "onTagIdsChange"
  | "onVersionChange"
  | "onRequireConfirmationChange"
>) {
  return (
    <>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">名称 *</span>
        <input
          className="input-field w-full"
          placeholder="例如：天气查询"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
        />
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
          <input
            className="input-field w-full"
            value={version}
            onChange={(e) => onVersionChange(e.target.value)}
          />
        </label>
        <label className="flex min-h-[42px] items-center justify-between rounded-lg border border-line-soft bg-surface px-3 text-xs">
          <span className="text-ink-muted">执行前需确认</span>
          <input
            type="checkbox"
            checked={requireConfirmation}
            onChange={(e) => onRequireConfirmationChange(e.target.checked)}
          />
        </label>
      </div>
    </>
  );
}

function HttpConfigFields({
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
}: Pick<
  Props,
  | "url"
  | "method"
  | "headersJson"
  | "bodyMode"
  | "timeoutSec"
  | "onUrlChange"
  | "onMethodChange"
  | "onHeadersJsonChange"
  | "onBodyModeChange"
  | "onTimeoutSecChange"
>) {
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
        <select
          className="input-field w-full"
          value={method}
          onChange={(e) => onMethodChange(e.target.value)}
        >
          <option value="GET">GET</option>
          <option value="POST">POST</option>
          <option value="PUT">PUT</option>
          <option value="PATCH">PATCH</option>
        </select>
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">Body</span>
        <select
          className="input-field w-full"
          value={bodyMode}
          onChange={(e) => onBodyModeChange(e.target.value as "json" | "none")}
        >
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

function ScriptConfigFields({
  scriptSource,
  timeoutSec,
  onScriptSourceChange,
  onTimeoutSecChange,
}: Pick<Props, "scriptSource" | "timeoutSec" | "onScriptSourceChange" | "onTimeoutSecChange">) {
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

function ToolEntityFields(props: Omit<
  Props,
  "open" | "editing" | "busy" | "onClose" | "onSubmit" | "onToolKindChange" | "kindTabs"
>) {
  const { toolKind, ...rest } = props;
  const isScript = toolKind === "script";
  const paramHint = isScript
    ? "传入 run(params) 的字典；试调用与 Agent 共用。"
    : "URL 可用 {{参数名}} 占位；试调用与 Agent 共用。";
  const execHint = isScript
    ? "MCP Runner 沙箱执行；须定义 run(params: dict) -> dict，禁止 import。"
    : "REST 调用配置；支持 URL 模板与 JSON Body。";

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)] lg:items-start">
      <aside className="space-y-4 lg:sticky lg:top-0">
        <Section title="基本信息">
          <BasicFields {...rest} />
        </Section>
      </aside>

      <div className="flex min-w-0 flex-col gap-5">
        <Section title="输入参数" hint={paramHint}>
          <ToolParameterEditor value={rest.parameters} onChange={rest.onParametersChange} />
        </Section>

        <Section
          title={isScript ? "Python 脚本" : "HTTP 配置"}
          hint={execHint}
          className={isScript ? "flex flex-col" : undefined}
        >
          {isScript ? (
            <ScriptConfigFields
              scriptSource={rest.scriptSource}
              timeoutSec={rest.timeoutSec}
              onScriptSourceChange={rest.onScriptSourceChange}
              onTimeoutSecChange={rest.onTimeoutSecChange}
            />
          ) : (
            <HttpConfigFields {...rest} />
          )}
        </Section>
      </div>
    </div>
  );
}

export function ToolCreateDialog({
  open,
  mode,
  kindTabs,
  toolKind,
  editing,
  slug,
  name,
  description,
  tagIds,
  version,
  requireConfirmation,
  parameters,
  url,
  method,
  headersJson,
  bodyMode,
  timeoutSec,
  scriptSource,
  busy,
  saveError = "",
  onClose,
  onDismissError,
  onSubmit,
  onToolKindChange,
  onSlugChange,
  onNameChange,
  onDescriptionChange,
  onTagIdsChange,
  onVersionChange,
  onRequireConfirmationChange,
  onParametersChange,
  onUrlChange,
  onMethodChange,
  onHeadersJsonChange,
  onBodyModeChange,
  onTimeoutSecChange,
  onScriptSourceChange,
}: Props) {
  const isHttp = toolKind === "http";
  const canSubmit =
    Boolean(name.trim() && slug.trim()) &&
    !busy &&
    (isHttp ? Boolean(url.trim()) : Boolean(scriptSource.trim()));
  const kindLocked = mode === "edit";

  return (
    <ResourceDialog
      open={open}
      size="sheet"
      contentMaxWidth="max-w-6xl"
      title={mode === "create" ? "新增工具" : `编辑 · ${editing?.name ?? ""}`}
      description={
        mode === "create"
          ? "左侧填写元数据，右侧配置参数与 HTTP / 脚本执行方式。"
          : undefined
      }
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
        {saveError ? (
          <KbPageAlert tone="error" message={saveError} onDismiss={onDismissError} />
        ) : null}
        <KindSelector
          kindTabs={kindTabs}
          toolKind={toolKind}
          kindLocked={kindLocked}
          onToolKindChange={onToolKindChange}
        />
        <ToolEntityFields
          mode={mode}
          toolKind={toolKind}
          slug={slug}
          name={name}
          description={description}
          tagIds={tagIds}
          version={version}
          requireConfirmation={requireConfirmation}
          parameters={parameters}
          url={url}
          method={method}
          headersJson={headersJson}
          bodyMode={bodyMode}
          timeoutSec={timeoutSec}
          scriptSource={scriptSource}
          onSlugChange={onSlugChange}
          onNameChange={onNameChange}
          onDescriptionChange={onDescriptionChange}
          onTagIdsChange={onTagIdsChange}
          onVersionChange={onVersionChange}
          onRequireConfirmationChange={onRequireConfirmationChange}
          onParametersChange={onParametersChange}
          onUrlChange={onUrlChange}
          onMethodChange={onMethodChange}
          onHeadersJsonChange={onHeadersJsonChange}
          onBodyModeChange={onBodyModeChange}
          onTimeoutSecChange={onTimeoutSecChange}
          onScriptSourceChange={onScriptSourceChange}
        />
      </div>
    </ResourceDialog>
  );
}
