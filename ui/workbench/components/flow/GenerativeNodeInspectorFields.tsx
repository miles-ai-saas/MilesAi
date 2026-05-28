"use client";

/**
 * 画布生图/生视频节点属性面板共用字段。
 * 模型列表来自流程编辑页 ``listModelConfigs``，按 ``model_type`` 过滤。
 */

import type { ModelConfig } from "@/lib/types";

export const IMAGE_SIZE_OPTIONS = ["1024x1024", "1280x720", "720x1280"] as const;
export const VIDEO_RESOLUTION_OPTIONS = ["720P", "1080P"] as const;

export function filterModelsByType(models: ModelConfig[], modelType: string) {
  return models.filter((m) => m.model_type === modelType);
}

export function modelLabel(models: ModelConfig[], id: unknown): string {
  if (!id) return "未选模型";
  const m = models.find((x) => x.id === String(id));
  return m?.name ?? String(id).slice(0, 8);
}

type FieldProps = {
  label: string;
  children: React.ReactNode;
};

export function InspectorField({ label, children }: FieldProps) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

type ModelSelectProps = {
  models: ModelConfig[];
  modelType: "image_gen" | "video_gen";
  value: string;
  onChange: (id: string | undefined) => void;
  required?: boolean;
};

export function GenerativeModelSelect({ models, modelType, value, onChange, required }: ModelSelectProps) {
  const options = filterModelsByType(models, modelType);
  return (
    <select className="input-field w-full text-sm" value={value} onChange={(e) => onChange(e.target.value || undefined)} required={required}>
      <option value="">{required ? "— 请选择 —" : "— 未选择 —"}</option>
      {options.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name}
          {!m.has_api_key ? "（缺 Key）" : ""}
        </option>
      ))}
    </select>
  );
}
