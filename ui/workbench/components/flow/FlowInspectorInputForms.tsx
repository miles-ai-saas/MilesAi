"use client";

import { InspectorField, type InspectorFormContext } from "@/components/flow/flow-inspector-shared";

export function TextInputInspectorForm({ data, patch, labelField }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="输入键 (input_key)">
        <input className="input-field w-full text-sm" value={String(data.input_key ?? "query")} onChange={(e) => patch({ input_key: e.target.value })} />
      </InspectorField>
      <InspectorField label="调试默认值 (可选)">
        <input
          className="input-field w-full text-sm"
          value={String(data.input_value ?? "")}
          onChange={(e) => patch({ input_value: e.target.value })}
          placeholder="覆盖 RunContext.inputs"
        />
      </InspectorField>
    </>
  );
}

export function StaticResponseInspectorForm({ data, patch, labelField }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <InspectorField label="回复文案">
        <textarea
          className="input-field min-h-[100px] w-full text-sm"
          value={String(data.text ?? "")}
          onChange={(e) => patch({ text: e.target.value })}
          placeholder="支持 {{用户提问}} / {{query}}"
        />
      </InspectorField>
    </>
  );
}

export function TextOutputInspectorForm({ labelField }: InspectorFormContext) {
  return <>{labelField}</>;
}
