"use client";

import { InspectorField, type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";

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
