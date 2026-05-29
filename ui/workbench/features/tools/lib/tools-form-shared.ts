import { DEFAULT_SCRIPT } from "@/features/tools/lib/tool-create-dialog-shared";
import type { ToolKindTab } from "@/features/tools/lib/tool-labels";
import type { CustomTool, ToolCreatePayload, ToolParameterSpec } from "@/lib/types";
import { defaultToolParams } from "@/features/tools/lib/tool-page-shared";

export type ToolFormState = {
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
};

export function emptyToolForm(): ToolFormState {
  return {
    toolKind: "http",
    slug: "",
    name: "",
    description: "",
    tagIds: [],
    version: "1.0.0",
    requireConfirmation: false,
    parameters: defaultToolParams(),
    url: "",
    method: "POST",
    headersJson: "{}",
    bodyMode: "json",
    timeoutSec: 15,
    scriptSource: DEFAULT_SCRIPT,
  };
}

export function toolFormFromCustomTool(detail: CustomTool): ToolFormState {
  return {
    toolKind: detail.tool_type === "script" ? "script" : "http",
    slug: detail.slug,
    name: detail.name,
    description: detail.description ?? "",
    tagIds: (detail.tags ?? []).map((t) => t.id),
    version: detail.version,
    requireConfirmation: detail.require_confirmation,
    parameters: detail.parameters ?? [],
    url: String((detail.config as { url?: string })?.url ?? ""),
    method: String((detail.config as { method?: string })?.method ?? "POST"),
    headersJson: JSON.stringify((detail.config as { headers?: object })?.headers ?? {}, null, 2),
    bodyMode: (detail.config as { body_mode?: string })?.body_mode === "none" ? "none" : "json",
    timeoutSec: Number((detail.config as { timeout_sec?: number })?.timeout_sec) || 15,
    scriptSource: String((detail.config as { source?: string })?.source ?? DEFAULT_SCRIPT),
  };
}

export function buildCustomToolPayload(form: ToolFormState): { payload: ToolCreatePayload } | { error: string } {
  let headers: Record<string, string> = {};
  if (form.toolKind === "http") {
    try {
      headers = form.headersJson.trim() ? JSON.parse(form.headersJson) : {};
    } catch {
      return { error: "Headers JSON 格式错误" };
    }
  }

  return {
    payload: {
      slug: form.slug.trim(),
      name: form.name.trim(),
      description: form.description.trim() || null,
      tool_type: form.toolKind,
      category_id: null,
      tag_ids: form.tagIds,
      version: form.version.trim() || "1.0.0",
      require_confirmation: form.requireConfirmation,
      parameters: form.parameters.filter((p) => p.name.trim()),
      config:
        form.toolKind === "script"
          ? {
              language: "python",
              source: form.scriptSource,
              timeout_sec: form.timeoutSec,
            }
          : {
              url: form.url.trim(),
              method: form.method,
              headers,
              body_mode: form.bodyMode,
              timeout_sec: form.timeoutSec,
            },
    },
  };
}
