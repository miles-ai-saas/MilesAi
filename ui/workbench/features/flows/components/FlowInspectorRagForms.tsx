"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";

export function RelevanceGradeInspectorForm({ data, patch, labelField, models }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="相关性阈值">
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          className="input-field w-full text-sm"
          value={Number(data.relevance_threshold ?? 0.35)}
          onChange={(e) => patch({ relevance_threshold: Number(e.target.value) })}
        />
      </InspectorField>
      <label className="mb-3 flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={Boolean(data.use_llm_grade)} onChange={(e) => patch({ use_llm_grade: e.target.checked })} />
        使用 LLM 复核（需配置模型）
      </label>
      {data.use_llm_grade && (
        <InspectorField label="评判模型 (可选)">
          <select
            className="input-field w-full text-sm"
            value={String(data.model_config_id ?? "")}
            onChange={(e) =>
              patch({
                model_config_id: e.target.value || undefined,
              })
            }
          >
            <option value="">— 使用运行上下文模型 —</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </InspectorField>
      )}
      <p className="text-[10px] leading-relaxed text-ink-muted">出边须连 good / poor / none 三支；good 与 poor 通常接生成链，none 接固定回复。</p>
    </>
  );
}


export function KnowledgeSearchInspectorForm({ data, patch, labelField, kbs }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="知识库 (可选，留空用调试运行所选)">
        <select className="input-field w-full text-sm" value={String(data.kb_id ?? "")} onChange={(e) => patch({ kb_id: e.target.value || undefined })}>
          <option value="">— 使用运行上下文 —</option>
          {kbs.map((kb) => (
            <option key={kb.id} value={kb.id}>
              {kb.name}
            </option>
          ))}
        </select>
      </InspectorField>
      <InspectorField label="top_k">
        <input
          type="number"
          min={1}
          max={50}
          className="input-field w-full text-sm"
          value={Number(data.top_k ?? 5)}
          onChange={(e) => patch({ top_k: Number(e.target.value) || 5 })}
        />
      </InspectorField>
      <InspectorField label="检索模式">
        <select className="input-field w-full text-sm" value={String(data.retrieval_mode ?? "default")} onChange={(e) => patch({ retrieval_mode: e.target.value })}>
          <option value="default">跟随知识库配置</option>
          <option value="vector">纯向量</option>
          <option value="hybrid">混合检索</option>
        </select>
      </InspectorField>
    </>
  );
}


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


export function LLMCallInspectorForm({ data, patch, labelField, models }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="模型 (可选)">
        <select
          className="input-field w-full text-sm"
          value={String(data.model_config_id ?? "")}
          onChange={(e) =>
            patch({
              model_config_id: e.target.value || undefined,
            })
          }
        >
          <option value="">— 使用智能体/运行上下文 —</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </InspectorField>
      <InspectorField label="temperature">
        <input
          type="number"
          min={0}
          max={2}
          step={0.1}
          className="input-field w-full text-sm"
          value={Number(data.temperature ?? 0.7)}
          onChange={(e) => patch({ temperature: Number(e.target.value) })}
        />
      </InspectorField>
      <InspectorField label="max_tokens">
        <input
          type="number"
          min={256}
          max={128000}
          step={256}
          className="input-field w-full text-sm"
          value={Number(data.max_tokens ?? 2048)}
          onChange={(e) => patch({ max_tokens: Number(e.target.value) || 2048 })}
        />
      </InspectorField>
    </>
  );
}

