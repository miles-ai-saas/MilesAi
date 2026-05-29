"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";
import { PlatformToolInspector } from "@/features/flows/components/PlatformToolInspector";
import { SubFlowInspector } from "@/features/flows/components/SubFlowInspector";

export function PlatformToolInspectorForm({ data, patch, labelField, toolCatalog }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <PlatformToolInspector data={data} catalog={toolCatalog} onPatch={patch} />
      <label className="mb-3 flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={data.merge_input !== false} onChange={(e) => patch({ merge_input: e.target.checked })} />
        合并上游输入到 params
      </label>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={data.confirmed !== false} onChange={(e) => patch({ confirmed: e.target.checked })} />
        已确认执行 (confirmed)
      </label>
    </>
  );
}

export function SubFlowInspectorForm({ data, patch, labelField, currentFlowId }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <SubFlowInspector data={data} currentFlowId={currentFlowId} onChange={patch} />
    </>
  );
}
