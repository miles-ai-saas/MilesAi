"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";

export function PromptTemplateInspectorForm({ node, data, patch, labelField, prompts }: InspectorFormContext) {
  const templateSource = (data.template_source as string | undefined) ?? (data.prompt_template_id ? "library" : "inline");
  const selectedPrompt = prompts.find((p) => p.id === String(data.prompt_template_id ?? ""));
  const setTemplateSource = (source: "library" | "inline") => {
    if (source === "library") {
      patch({
        template_source: "library",
        template: undefined,
      });
    } else {
      patch({
        template_source: "inline",
        prompt_template_id: undefined,
        template: data.template ?? "基于以下资料回答用户问题。\n\n资料：\n{{检索结果}}\n\n问题：{{用户提问}}",
      });
    }
  };
  return (
    <>
      {labelField}
      <InspectorField label="来源">
        <div className="flex flex-col gap-1.5 text-sm">
          <label className="flex cursor-pointer items-center gap-2">
            <input type="radio" name={`prompt-source-${node.id}`} checked={templateSource === "library"} onChange={() => setTemplateSource("library")} />
            <span>模板库（运行时引用）</span>
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input type="radio" name={`prompt-source-${node.id}`} checked={templateSource === "inline"} onChange={() => setTemplateSource("inline")} />
            <span>自定义内联</span>
          </label>
        </div>
      </InspectorField>
      {templateSource === "library" ? (
        <>
          <InspectorField label="提示词模板">
            <select
              className="input-field w-full text-sm"
              value={String(data.prompt_template_id ?? "")}
              onChange={(e) =>
                patch({
                  template_source: "library",
                  prompt_template_id: e.target.value || undefined,
                  template: undefined,
                })
              }
            >
              <option value="">— 请选择 —</option>
              {prompts.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {!p.is_active ? "（已停用）" : ""}
                </option>
              ))}
            </select>
          </InspectorField>
          {selectedPrompt ? (
            <InspectorField label="当前内容预览（只读，运行时会读取最新版本）">
              <textarea readOnly className="input-field min-h-[120px] w-full cursor-default font-mono text-xs text-ink-muted" value={selectedPrompt.content} />
            </InspectorField>
          ) : (
            <p className="mb-3 text-xs text-amber-700">请选择模板库中的提示词；保存后运行时会 live 引用最新 content。</p>
          )}
        </>
      ) : (
        <InspectorField label="模板">
          <textarea
            className="input-field min-h-[140px] w-full font-mono text-xs"
            value={String(data.template ?? "")}
            onChange={(e) =>
              patch({
                template_source: "inline",
                template: e.target.value,
                prompt_template_id: undefined,
              })
            }
            placeholder="{{检索结果}}、{{用户提问}}"
          />
        </InspectorField>
      )}
      <p className="text-[11px] leading-relaxed text-ink-faint">
        占位符：{"{{检索结果}}"}、{"{{用户提问}}"}、{"{{query}}"}、{"{{context}}"}。 智能体配置中的系统提示词会拼在本模板之前。
      </p>
    </>
  );
}
