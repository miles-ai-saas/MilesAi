"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ToolParameterEditor } from "@/components/tool/ToolParameterEditor";
import { TagPicker } from "@/components/tag/TagPicker";
import { TOOL_KIND_TABS, type ToolKindTab } from "@/lib/tool-labels";
import type { CustomTool, ToolParameterSpec } from "@/lib/types";

export type ToolDialogMode = "create" | "edit";

export const DEFAULT_SCRIPT = `def run(params: dict) -> dict:
    """params 对应下方输入参数 schema"""
    # return {"result": params.get("query")}
    raise NotImplementedError("请实现 run(params)")`;

type Props = {
  open: boolean;
  mode: ToolDialogMode;
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
  onClose: () => void;
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface-muted/30 p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
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
          placeholder="例如：文本处理"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">编号 *</span>
        <input
          className="input-field w-full font-mono"
          placeholder="text_transform"
          value={slug}
          disabled={mode === "edit"}
          onChange={(e) => onSlugChange(e.target.value.toLowerCase())}
        />
      </label>
      <label className="block text-xs">
        <span className="mb-1 block text-ink-muted">描述</span>
        <textarea
          className="input-field min-h-[64px] w-full"
          placeholder="供 LLM 与使用者理解工具用途"
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
        <label className="flex items-end justify-between rounded-lg border border-line-soft bg-surface px-3 py-2 text-xs">
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

function ToolEntityFields(props: Omit<
  Props,
  "open" | "editing" | "busy" | "onClose" | "onSubmit" | "onToolKindChange"
>) {
  const {
    mode,
    toolKind,
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
  } = props;
  const isScript = toolKind === "script";

  return (
    <div className="space-y-4">
      <Section title="基本信息">
        <BasicFields
          mode={mode}
          slug={slug}
          name={name}
          description={description}
          tagIds={tagIds}
          version={version}
          requireConfirmation={requireConfirmation}
          onSlugChange={onSlugChange}
          onNameChange={onNameChange}
          onDescriptionChange={onDescriptionChange}
          onTagIdsChange={onTagIdsChange}
          onVersionChange={onVersionChange}
          onRequireConfirmationChange={onRequireConfirmationChange}
        />
      </Section>

      <Section title="输入参数">
        <p className="-mt-1 mb-2 text-xs text-ink-faint">
          试调用与 Agent function calling 共用
          {!isScript ? "；URL 中可用 {{参数名}} 占位" : "；传入 run(params) 的 params 字典"}。
        </p>
        <ToolParameterEditor value={parameters} onChange={onParametersChange} />
      </Section>

      {isScript ? (
        <Section title="Python 脚本">
          <p className="-mt-1 mb-2 text-xs text-ink-faint">
            在 MCP Runner 沙箱内执行；须定义{" "}
            <code className="font-mono">run(params: dict) -&gt; dict</code>，禁止 import 与危险内置调用。
          </p>
          <label className="block text-xs">
            <span className="mb-1 block text-ink-muted">源码 *</span>
            <textarea
              className="input-field min-h-[200px] w-full font-mono text-xs"
              spellCheck={false}
              value={scriptSource}
              onChange={(e) => onScriptSourceChange(e.target.value)}
            />
          </label>
          <label className="block text-xs sm:max-w-xs">
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
        </Section>
      ) : (
        <Section title="HTTP 配置">
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
            <label className="block text-xs sm:col-span-1">
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
            <label className="block text-xs sm:col-span-1">
              <span className="mb-1 block text-ink-muted">Body</span>
              <select
                className="input-field w-full"
                value={bodyMode}
                onChange={(e) => onBodyModeChange(e.target.value as "json" | "none")}
              >
                <option value="json">JSON（默认）</option>
                <option value="none">无 Body</option>
              </select>
            </label>
            <label className="block text-xs sm:col-span-1">
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
              className="input-field min-h-[72px] w-full font-mono text-xs"
              placeholder='{"Authorization": "Bearer xxx"}'
              value={headersJson}
              onChange={(e) => onHeadersJsonChange(e.target.value)}
            />
          </label>
        </Section>
      )}
    </div>
  );
}

export function ToolCreateDialog({
  open,
  mode,
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
  onClose,
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
      title={mode === "create" ? "新增工具" : `编辑 · ${editing?.name ?? ""}`}
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
      {!kindLocked && (
        <div className="mb-5 grid gap-2 sm:grid-cols-2">
          {TOOL_KIND_TABS.map((tab) => {
            const active = toolKind === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                disabled={!tab.available}
                onClick={() => tab.available && onToolKindChange(tab.key)}
                className={`rounded-xl border px-4 py-3 text-left transition ${
                  active
                    ? "border-brand bg-brand-light/40 ring-1 ring-brand/30"
                    : tab.available
                      ? "border-line bg-surface hover:border-brand/40"
                      : "cursor-not-allowed border-line bg-surface-muted/50 opacity-75"
                }`}
              >
                <span className="text-sm font-medium text-ink">{tab.label}</span>
                <p className="mt-1 text-xs text-ink-muted">{tab.hint}</p>
              </button>
            );
          })}
        </div>
      )}

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
    </ResourceDialog>
  );
}
