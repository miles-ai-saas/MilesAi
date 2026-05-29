"use client";

import { AttachmentIdField } from "@/features/attachments";
import {
  GenerativeModelSelect,
  IMAGE_SIZE_OPTIONS,
  InspectorField as GenerativeInspectorField,
  VIDEO_RESOLUTION_OPTIONS,
  modelLabel,
} from "@/features/flows/components/GenerativeNodeInspectorFields";
import { type InspectorFormContext } from "@/features/flows/components/flow-inspector-shared";

export function ImageGenerateInspectorForm({ data, patch, labelField, models }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <GenerativeInspectorField label="生图模型 (image_gen) *">
        <GenerativeModelSelect
          models={models}
          modelType="image_gen"
          value={String(data.model_config_id ?? "")}
          onChange={(id) => patch({ model_config_id: id ?? "" })}
          required
        />
      </GenerativeInspectorField>
      {data.model_config_id && <p className="-mt-2 mb-3 text-[10px] text-ink-muted">已选：{modelLabel(models, data.model_config_id)}</p>}
      <GenerativeInspectorField label="固定 prompt（可选，留空则用上游 prompt/input）">
        <textarea
          className="input-field min-h-[72px] w-full text-sm"
          value={String(data.prompt ?? "")}
          onChange={(e) => patch({ prompt: e.target.value })}
          placeholder="例如：一只在沙滩上的猫"
        />
      </GenerativeInspectorField>
      <GenerativeInspectorField label="尺寸">
        <select className="input-field w-full text-sm" value={String(data.size ?? "1024x1024")} onChange={(e) => patch({ size: e.target.value })}>
          {IMAGE_SIZE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </GenerativeInspectorField>
      <GenerativeInspectorField label="生成张数 n">
        <input
          type="number"
          min={1}
          max={4}
          className="input-field w-full text-sm"
          value={Number(data.n ?? 1)}
          onChange={(e) => patch({ n: Math.min(4, Math.max(1, Number(e.target.value) || 1)) })}
        />
      </GenerativeInspectorField>
      <GenerativeInspectorField label="参考图（图生图，可选）">
        <AttachmentIdField
          value={String(data.image_attachment_id ?? "")}
          onChange={(id) => patch({ image_attachment_id: id })}
          uploadPurpose="flow"
          placeholder="选择/上传，或由入边 image_attachment_id 传入"
        />
      </GenerativeInspectorField>
      <p className="text-[10px] leading-relaxed text-ink-muted">文生图：prompt/input + image_gen 模型。图生图：另传参考图（豆包 SeedEdit / 万相 ref_image）。</p>
    </>
  );
}

export function VideoGenerateInspectorForm({ data, patch, labelField, models }: InspectorFormContext) {
  return (
    <>
      {labelField}
      <GenerativeInspectorField label="生视频模型 (video_gen) *">
        <GenerativeModelSelect
          models={models}
          modelType="video_gen"
          value={String(data.model_config_id ?? "")}
          onChange={(id) => patch({ model_config_id: id ?? "" })}
          required
        />
      </GenerativeInspectorField>
      {data.model_config_id && <p className="-mt-2 mb-3 text-[10px] text-ink-muted">已选：{modelLabel(models, data.model_config_id)}（万相优先）</p>}
      <GenerativeInspectorField label="固定 prompt（可选）">
        <textarea
          className="input-field min-h-[72px] w-full text-sm"
          value={String(data.prompt ?? "")}
          onChange={(e) => patch({ prompt: e.target.value })}
          placeholder="例如：海浪拍打礁石，慢镜头"
        />
      </GenerativeInspectorField>
      <GenerativeInspectorField label="时长（秒）">
        <input
          type="number"
          min={3}
          max={15}
          className="input-field w-full text-sm"
          value={Number(data.duration ?? 5)}
          onChange={(e) => patch({ duration: Number(e.target.value) || 5 })}
        />
      </GenerativeInspectorField>
      <GenerativeInspectorField label="分辨率">
        <select className="input-field w-full text-sm" value={String(data.resolution ?? "720P")} onChange={(e) => patch({ resolution: e.target.value })}>
          {VIDEO_RESOLUTION_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </GenerativeInspectorField>
      <GenerativeInspectorField label="首帧图（图生视频 / 首尾帧，可选）">
        <AttachmentIdField
          value={String(data.image_attachment_id ?? "")}
          onChange={(id) => patch({ image_attachment_id: id })}
          uploadPurpose="flow"
          placeholder="选择/上传，或由入边传入"
        />
      </GenerativeInspectorField>
      <GenerativeInspectorField label="尾帧图（首尾帧生视频，可选）">
        <AttachmentIdField
          value={String(data.last_frame_attachment_id ?? "")}
          onChange={(id) => patch({ last_frame_attachment_id: id })}
          uploadPurpose="flow"
          placeholder="须与首帧同时提供；或由入边传入"
        />
      </GenerativeInspectorField>
      <p className="text-[10px] leading-relaxed text-ink-muted">
        文生视频仅 prompt。首帧图生视频：首帧 attachment。首尾帧：首帧+尾帧（万相 wan2.7-i2v / 豆包 Seedance lite i2v）。
      </p>
    </>
  );
}
