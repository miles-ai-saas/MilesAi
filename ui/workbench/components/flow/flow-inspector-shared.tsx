"use client";

import type { Node } from "@xyflow/react";
import type { KnowledgeBase, ModelConfig, PromptTemplate, ToolCatalogItem } from "@/lib/types";

export function InspectorField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

export type InspectorFormContext = {
  node: Node;
  data: Record<string, unknown>;
  patch: (p: Record<string, unknown>) => void;
  labelField: React.ReactNode;
  kbs: KnowledgeBase[];
  models: ModelConfig[];
  prompts: PromptTemplate[];
  toolCatalog: ToolCatalogItem[];
  currentFlowId?: string;
};

export function makeLabelField(data: Record<string, unknown>, patch: (p: Record<string, unknown>) => void) {
  return (
    <InspectorField label="显示名称">
      <input className="input-field w-full text-sm" value={String(data.label ?? "")} onChange={(e) => patch({ label: e.target.value })} />
    </InspectorField>
  );
}
