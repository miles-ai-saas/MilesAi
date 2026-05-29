"use client";

import { ToolParameterEditor } from "@/features/tools/components/ToolParameterEditor";
import {
  ToolCreateDialogBasicFields,
  ToolCreateDialogHttpFields,
  ToolCreateDialogScriptFields,
} from "@/features/tools/components/ToolCreateDialogFields";
import { ToolCreateDialogSection, type ToolDialogMode } from "@/features/tools/components/ToolCreateDialog";
import type { ToolKindTab } from "@/features/tools/lib/tool-labels";
import type { ToolParameterSpec } from "@/lib/types";

export type ToolCreateDialogEntityFormProps = {
  mode: ToolDialogMode;
  toolKind: ToolKindTab;
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

export function ToolCreateDialogEntityForm(props: ToolCreateDialogEntityFormProps) {
  const { toolKind, parameters, onParametersChange, ...fieldProps } = props;
  const isScript = toolKind === "script";
  const paramHint = isScript ? "传入 run(params) 的字典；试调用与 Agent 共用。" : "URL 可用 {{参数名}} 占位；试调用与 Agent 共用。";
  const execHint = isScript ? "MCP Runner 沙箱执行；须定义 run(params: dict) -> dict，禁止 import。" : "REST 调用配置；支持 URL 模板与 JSON Body。";

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)] lg:items-start">
      <aside className="space-y-4 lg:sticky lg:top-0">
        <ToolCreateDialogSection title="基本信息">
          <ToolCreateDialogBasicFields {...fieldProps} />
        </ToolCreateDialogSection>
      </aside>

      <div className="flex min-w-0 flex-col gap-5">
        <ToolCreateDialogSection title="输入参数" hint={paramHint}>
          <ToolParameterEditor value={parameters} onChange={onParametersChange} />
        </ToolCreateDialogSection>

        <ToolCreateDialogSection title={isScript ? "Python 脚本" : "HTTP 配置"} hint={execHint} className={isScript ? "flex flex-col" : undefined}>
          {isScript ? (
            <ToolCreateDialogScriptFields
              scriptSource={fieldProps.scriptSource}
              timeoutSec={fieldProps.timeoutSec}
              onScriptSourceChange={fieldProps.onScriptSourceChange}
              onTimeoutSecChange={fieldProps.onTimeoutSecChange}
            />
          ) : (
            <ToolCreateDialogHttpFields {...fieldProps} />
          )}
        </ToolCreateDialogSection>
      </div>
    </div>
  );
}
