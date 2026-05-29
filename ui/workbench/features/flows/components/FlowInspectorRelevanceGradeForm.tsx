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
