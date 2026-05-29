"use client";

import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";
import type { ModelsPageVm } from "@/features/models/hooks/use-models-page";

const MODEL_TYPE_LABELS: Record<string, string> = {
  llm: "大语言模型",
  reasoning: "推理模型",
  vision: "图像理解",
  embedding: "向量化",
  rerank: "重排序",
  image_gen: "图像生成",
  video_gen: "视频生成",
  asr: "语音识别",
  tts: "语音合成",
  other: "其它",
};

const SOURCE_LABELS: Record<string, string> = {
  builtin: "内置模型",
  custom: "自定义模型",
};

function vendorLabel(vendor: string, meta?: ModelCatalogMeta | null): string {
  return meta?.vendors.find((v) => v.value === vendor)?.label ?? vendor;
}

function modelTypeLabel(t: string, meta?: ModelCatalogMeta | null): string {
  return meta?.model_types.find((x) => x.value === t)?.label ?? MODEL_TYPE_LABELS[t] ?? t;
}

function credentialHint(m: ModelConfig): string {
  if (m.source === "custom") {
    if (m.credential_status === "tenant") return "已配置 API Key，可直接绑定使用";
    return "请在编辑时填写 API Key 后方可调用";
  }
  if (m.credential_status === "platform") return "平台已配置密钥，可直接绑定使用";
  if (m.credential_status === "tenant") return "当前使用租户自有 Key（优先于平台密钥）";
  return "平台尚未为该模型配置密钥，请联系管理员；若您自有 Key，可选用下方「使用自有 Key」";
}

function isCustomMissingKey(m: ModelConfig): boolean {
  return m.source === "custom" && m.credential_status === "missing";
}

function isBuiltinPlatformMissing(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "missing";
}

function isBuiltinReady(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "platform";
}

function isBuiltinByok(m: ModelConfig): boolean {
  return m.source === "builtin" && m.credential_status === "tenant";
}

export function ModelCatalogGrid({ vm }: { vm: ModelsPageVm }) {
  if (vm.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }
  if (vm.items.length === 0) {
    return <p className="text-sm text-ink-muted">暂无匹配的模型。</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {vm.items.map((m) => (
        <article key={m.id} className="resource-card relative !min-h-0 flex-col !items-stretch !p-4">
          {m.badge === "latest" && <span className="absolute right-3 top-3 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">最新</span>}
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded bg-surface-muted px-2 py-0.5 text-xs font-medium text-ink">{vendorLabel(m.vendor, vm.meta)}</span>
            <span className="text-xs text-ink-muted">{m.model_code ?? m.model_name}</span>
          </div>
          <h3 className="pr-12 text-base font-semibold text-ink">{m.name}</h3>
          <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-ink-muted">{m.description ?? "暂无描述"}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded border border-border px-2 py-0.5 text-xs text-ink-muted">{modelTypeLabel(m.model_type, vm.meta)}</span>
            <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-xs text-brand">{SOURCE_LABELS[m.source]}</span>
            {isBuiltinReady(m) && <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">可直接使用</span>}
            {isBuiltinByok(m) && <span className="rounded border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs text-sky-800">自有 Key</span>}
            {isBuiltinPlatformMissing(m) && (
              <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">平台未配置</span>
            )}
            {isCustomMissingKey(m) && <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">待配置 Key</span>}
          </div>
          <p className="mt-2 text-xs text-ink-muted">{credentialHint(m)}</p>
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
            {m.source === "builtin" ? (
              isBuiltinByok(m) ? (
                <>
                  <button type="button" className="btn-ghost text-xs" onClick={() => vm.openCred(m)}>
                    更新自有 Key
                  </button>
                  <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={() => vm.onClearBuiltinByok(m)}>
                    恢复平台密钥
                  </button>
                </>
              ) : (
                <button type="button" className="btn-ghost text-xs" onClick={() => vm.openCred(m)}>
                  使用自有 Key（可选）
                </button>
              )
            ) : (
              <>
                <button type="button" className="btn-ghost text-xs" onClick={() => vm.openEdit(m)}>
                  编辑
                </button>
                <button type="button" className="btn-ghost text-xs text-red-600" onClick={() => vm.onDelete(m)}>
                  删除
                </button>
              </>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
