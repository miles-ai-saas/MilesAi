"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";

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
