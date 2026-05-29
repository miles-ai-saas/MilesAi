"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";
import { CONDITION_MODES, MERGE_STRATEGIES } from "@/features/flows/lib/flow-node-schemas";

export function ConditionBranchInspectorForm({ data, patch, labelField }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="模式">
        <select className="input-field w-full text-sm" value={String(data.mode ?? "has_hits")} onChange={(e) => patch({ mode: e.target.value })}>
          {CONDITION_MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </InspectorField>
      {data.mode === "score_above" && (
        <InspectorField label="阈值">
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            className="input-field w-full text-sm"
            value={Number(data.threshold ?? 0.35)}
            onChange={(e) => patch({ threshold: Number(e.target.value) })}
          />
        </InspectorField>
      )}
      {data.mode === "text_contains" && (
        <InspectorField label="关键词">
          <input className="input-field w-full text-sm" value={String(data.keyword ?? "")} onChange={(e) => patch({ keyword: e.target.value })} />
        </InspectorField>
      )}
    </>
  );
}

export function ParallelJoinInspectorForm({ data, patch, labelField }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="合并策略">
        <select className="input-field w-full text-sm" value={String(data.merge_strategy ?? "dict")} onChange={(e) => patch({ merge_strategy: e.target.value })}>
          {MERGE_STRATEGIES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </InspectorField>
    </>
  );
}
