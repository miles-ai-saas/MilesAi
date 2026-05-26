"use client";

/** 流程节点属性面板（链路 §6，见 flow-node-schemas.ts）。 */
import type { Node } from "@xyflow/react";
import type { NodeType } from "@/lib/flow-nodes";
import { CONDITION_MODES, MERGE_STRATEGIES } from "@/lib/flow-node-schemas";
import {
  GenerativeModelSelect,
  IMAGE_SIZE_OPTIONS,
  InspectorField,
  VIDEO_RESOLUTION_OPTIONS,
  modelLabel,
} from "@/components/flow/GenerativeNodeInspectorFields";
import { PlatformToolInspector } from "@/components/flow/PlatformToolInspector";
import type { KnowledgeBase, ModelConfig, ToolCatalogItem } from "@/lib/types";

type FlowStep = Record<string, unknown>;

interface FlowNodeInspectorProps {
  node: Node | null;
  kbs: KnowledgeBase[];
  models: ModelConfig[];
  toolCatalog: ToolCatalogItem[];
  onChange: (nodeId: string, patch: Record<string, unknown>) => void;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

function InspectorForm({
  node,
  kbs,
  models,
  toolCatalog,
  onChange,
}: Required<FlowNodeInspectorProps>) {
  const type = node.type as NodeType;
  const data = node.data as Record<string, unknown>;
  const patch = (p: Record<string, unknown>) => onChange(node.id, p);

  const labelField = (
    <Field label="显示名称">
      <input
        className="input-field w-full text-sm"
        value={String(data.label ?? "")}
        onChange={(e) => patch({ label: e.target.value })}
      />
    </Field>
  );

  switch (type) {
    case "TextInput":
      return (
        <>
          {labelField}
          <Field label="输入键 (input_key)">
            <input
              className="input-field w-full text-sm"
              value={String(data.input_key ?? "query")}
              onChange={(e) => patch({ input_key: e.target.value })}
            />
          </Field>
          <Field label="调试默认值 (可选)">
            <input
              className="input-field w-full text-sm"
              value={String(data.input_value ?? "")}
              onChange={(e) => patch({ input_value: e.target.value })}
              placeholder="覆盖 RunContext.inputs"
            />
          </Field>
        </>
      );
    case "RelevanceGrade":
      return (
        <>
          {labelField}
          <Field label="相关性阈值">
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              className="input-field w-full text-sm"
              value={Number(data.relevance_threshold ?? 0.35)}
              onChange={(e) =>
                patch({ relevance_threshold: Number(e.target.value) })
              }
            />
          </Field>
          <label className="mb-3 flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={Boolean(data.use_llm_grade)}
              onChange={(e) => patch({ use_llm_grade: e.target.checked })}
            />
            使用 LLM 复核（需配置模型）
          </label>
          {data.use_llm_grade && (
            <Field label="评判模型 (可选)">
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
            </Field>
          )}
          <p className="text-[10px] leading-relaxed text-ink-muted">
            出边须连 good / poor / none 三支；good 与 poor 通常接生成链，none 接固定回复。
          </p>
        </>
      );
    case "StaticResponse":
      return (
        <>
          {labelField}
          <Field label="回复文案">
            <textarea
              className="input-field min-h-[100px] w-full text-sm"
              value={String(data.text ?? "")}
              onChange={(e) => patch({ text: e.target.value })}
              placeholder="支持 {{用户提问}} / {{query}}"
            />
          </Field>
        </>
      );
    case "KnowledgeSearch":
      return (
        <>
          {labelField}
          <Field label="知识库 (可选，留空用调试运行所选)">
            <select
              className="input-field w-full text-sm"
              value={String(data.kb_id ?? "")}
              onChange={(e) =>
                patch({ kb_id: e.target.value || undefined })
              }
            >
              <option value="">— 使用运行上下文 —</option>
              {kbs.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="top_k">
            <input
              type="number"
              min={1}
              max={50}
              className="input-field w-full text-sm"
              value={Number(data.top_k ?? 5)}
              onChange={(e) => patch({ top_k: Number(e.target.value) || 5 })}
            />
          </Field>
          <Field label="检索模式">
            <select
              className="input-field w-full text-sm"
              value={String(data.retrieval_mode ?? "default")}
              onChange={(e) => patch({ retrieval_mode: e.target.value })}
            >
              <option value="default">跟随知识库配置</option>
              <option value="vector">纯向量</option>
              <option value="hybrid">混合检索</option>
            </select>
          </Field>
        </>
      );
    case "PromptTemplate":
      return (
        <>
          {labelField}
          <Field label="模板">
            <textarea
              className="input-field min-h-[140px] w-full font-mono text-xs"
              value={String(data.template ?? "")}
              onChange={(e) => patch({ template: e.target.value })}
              placeholder="{{检索结果}}、{{用户提问}}"
            />
          </Field>
        </>
      );
    case "LLMCall":
      return (
        <>
          {labelField}
          <Field label="模型 (可选)">
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
          </Field>
          <Field label="temperature">
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              className="input-field w-full text-sm"
              value={Number(data.temperature ?? 0.7)}
              onChange={(e) =>
                patch({ temperature: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="max_tokens">
            <input
              type="number"
              min={256}
              max={128000}
              step={256}
              className="input-field w-full text-sm"
              value={Number(data.max_tokens ?? 2048)}
              onChange={(e) =>
                patch({ max_tokens: Number(e.target.value) || 2048 })
              }
            />
          </Field>
        </>
      );
    case "ConditionBranch":
      return (
        <>
          {labelField}
          <Field label="模式">
            <select
              className="input-field w-full text-sm"
              value={String(data.mode ?? "has_hits")}
              onChange={(e) => patch({ mode: e.target.value })}
            >
              {CONDITION_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </Field>
          {data.mode === "score_above" && (
            <Field label="阈值">
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="input-field w-full text-sm"
                value={Number(data.threshold ?? 0.35)}
                onChange={(e) =>
                  patch({ threshold: Number(e.target.value) })
                }
              />
            </Field>
          )}
          {data.mode === "text_contains" && (
            <Field label="关键词">
              <input
                className="input-field w-full text-sm"
                value={String(data.keyword ?? "")}
                onChange={(e) => patch({ keyword: e.target.value })}
              />
            </Field>
          )}
        </>
      );
    case "ParallelJoin":
      return (
        <>
          {labelField}
          <Field label="合并策略">
            <select
              className="input-field w-full text-sm"
              value={String(data.merge_strategy ?? "dict")}
              onChange={(e) => patch({ merge_strategy: e.target.value })}
            >
              {MERGE_STRATEGIES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </Field>
        </>
      );
    case "PlatformTool":
      return (
        <>
          {labelField}
          <PlatformToolInspector
            data={data}
            catalog={toolCatalog}
            onPatch={patch}
          />
          <label className="mb-3 flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={data.merge_input !== false}
              onChange={(e) => patch({ merge_input: e.target.checked })}
            />
            合并上游输入到 params
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={data.confirmed !== false}
              onChange={(e) => patch({ confirmed: e.target.checked })}
            />
            已确认执行 (confirmed)
          </label>
        </>
      );
    case "TextOutput":
      return <>{labelField}</>;
    // --- 多模态生成（对应 backend flow_runtime.nodes.image_generate / video_generate）---
    case "ImageGenerate":
      return (
        <>
          {labelField}
          <InspectorField label="生图模型 (image_gen) *">
            <GenerativeModelSelect
              models={models}
              modelType="image_gen"
              value={String(data.model_config_id ?? "")}
              onChange={(id) => patch({ model_config_id: id ?? "" })}
              required
            />
          </InspectorField>
          {data.model_config_id && (
            <p className="-mt-2 mb-3 text-[10px] text-ink-muted">
              已选：{modelLabel(models, data.model_config_id)}
            </p>
          )}
          <InspectorField label="固定 prompt（可选，留空则用上游 prompt/input）">
            <textarea
              className="input-field min-h-[72px] w-full text-sm"
              value={String(data.prompt ?? "")}
              onChange={(e) => patch({ prompt: e.target.value })}
              placeholder="例如：一只在沙滩上的猫"
            />
          </InspectorField>
          <InspectorField label="尺寸">
            <select
              className="input-field w-full text-sm"
              value={String(data.size ?? "1024x1024")}
              onChange={(e) => patch({ size: e.target.value })}
            >
              {IMAGE_SIZE_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </InspectorField>
          <InspectorField label="生成张数 n">
            <input
              type="number"
              min={1}
              max={4}
              className="input-field w-full text-sm"
              value={Number(data.n ?? 1)}
              onChange={(e) => patch({ n: Math.min(4, Math.max(1, Number(e.target.value) || 1)) })}
            />
          </InspectorField>
          <p className="text-[10px] leading-relaxed text-ink-muted">
            入边：prompt 或 input 接收上游文案；出边 output 为图片 attachment 元数据。
          </p>
        </>
      );
    case "VideoGenerate":
      return (
        <>
          {labelField}
          <InspectorField label="生视频模型 (video_gen) *">
            <GenerativeModelSelect
              models={models}
              modelType="video_gen"
              value={String(data.model_config_id ?? "")}
              onChange={(id) => patch({ model_config_id: id ?? "" })}
              required
            />
          </InspectorField>
          {data.model_config_id && (
            <p className="-mt-2 mb-3 text-[10px] text-ink-muted">
              已选：{modelLabel(models, data.model_config_id)}（万相优先）
            </p>
          )}
          <InspectorField label="固定 prompt（可选）">
            <textarea
              className="input-field min-h-[72px] w-full text-sm"
              value={String(data.prompt ?? "")}
              onChange={(e) => patch({ prompt: e.target.value })}
              placeholder="例如：海浪拍打礁石，慢镜头"
            />
          </InspectorField>
          <InspectorField label="时长（秒）">
            <input
              type="number"
              min={3}
              max={15}
              className="input-field w-full text-sm"
              value={Number(data.duration ?? 5)}
              onChange={(e) => patch({ duration: Number(e.target.value) || 5 })}
            />
          </InspectorField>
          <InspectorField label="分辨率">
            <select
              className="input-field w-full text-sm"
              value={String(data.resolution ?? "720P")}
              onChange={(e) => patch({ resolution: e.target.value })}
            >
              {VIDEO_RESOLUTION_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </InspectorField>
          <InspectorField label="首帧 attachment_id（图生视频，可选）">
            <input
              className="input-field w-full font-mono text-xs"
              value={String(data.image_attachment_id ?? "")}
              onChange={(e) =>
                patch({ image_attachment_id: e.target.value.trim() || "" })
              }
              placeholder="或由入边 image_attachment_id 传入"
            />
          </InspectorField>
          <p className="text-[10px] leading-relaxed text-ink-muted">
            运行会阻塞轮询直至完成（可达数分钟）。入边：prompt / input；图生视频可接
            image_attachment_id。
          </p>
        </>
      );
    default:
      return (
        <p className="text-xs text-ink-muted">
          节点类型 {String(type)} 暂无属性表单
        </p>
      );
  }
}

export function FlowNodeInspector(props: FlowNodeInspectorProps) {
  const { node } = props;
  if (!node) {
    return (
      <aside className="flex w-64 shrink-0 flex-col border-l border-line bg-surface p-3 sm:w-72">
        <p className="text-xs font-semibold uppercase text-ink-faint">节点属性</p>
        <p className="mt-4 text-sm text-ink-muted">选中画布上的节点以编辑配置</p>
      </aside>
    );
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-l border-line bg-surface sm:w-72">
      <div className="border-b border-line bg-surface-muted/50 px-3 py-2.5">
        <p className="text-xs font-semibold uppercase text-ink-faint">节点属性</p>
        <p className="mt-1 truncate text-sm font-medium text-ink">
          {String((node.data as Record<string, unknown>)?.label ?? node.type)}
        </p>
        <p className="font-mono text-[10px] text-ink-faint">{node.type}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <InspectorForm {...props} node={node} />
      </div>
    </aside>
  );
}

export type FlowCompileErrorDetail = {
  code: string;
  message: string;
  node_id?: string | null;
};

export function formatCompileErrors(
  errors: string[],
  details?: FlowCompileErrorDetail[],
): string {
  if (details?.length) {
    return details
      .map((d) => (d.node_id ? `[${d.node_id}] ${d.message}` : d.message))
      .join("\n");
  }
  return errors.join("\n");
}

function stepOutputLine(s: FlowStep): string {
  const art = s.artifact;
  if (art && typeof art === "object") {
    const kind = (art as Record<string, unknown>).kind;
    const id = (art as Record<string, unknown>).attachment_id;
    if (kind === "image" || kind === "video") {
      const short =
        typeof id === "string" && id.length > 8 ? `${id.slice(0, 8)}…` : id;
      return `\n  → 已生成${kind === "video" ? "视频" : "图片"}（${short}，见上方预览）`;
    }
  }
  return s.output_preview ? `\n  ${s.output_preview}` : "";
}

export function formatFlowSteps(steps: FlowStep[]): string {
  return steps
    .map((s, i) => {
      const t = String(s.type ?? "step");
      const nid = s.node_id ? ` · ${s.node_id}` : "";
      const nt = s.node_type ? ` (${s.node_type})` : "";
      return `${i + 1}. [${t}]${nid}${nt}${stepOutputLine(s)}`;
    })
    .join("\n");
}
