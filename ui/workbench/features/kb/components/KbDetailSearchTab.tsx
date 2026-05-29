"use client";

import { retrievalModeLabel } from "@/lib/kb-labels";
import type { KbDetailPageVm } from "@/hooks/use-kb-detail-page";

export function KbDetailSearchTab({ vm }: { vm: KbDetailPageVm }) {
  const kb = vm.kb!;
  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <h2 className="text-sm font-semibold text-ink">检索测试</h2>
      <p className="mt-1 text-xs text-ink-faint">
        默认使用本库配置（{retrievalModeLabel(kb.retrieval_mode, vm.kbMeta?.retrieval_modes)}）。 专有名词、编号可尝试「混合」。文本搜图：勾选「图片」+ OCR
        检索；真·以图搜图：勾选「CLIP 视觉相似度」并选择参考图或输入描述。
      </p>
      <div className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1">
            <span className="sr-only">检索问题</span>
            <input
              className="input-field w-full"
              value={vm.searchQ}
              onChange={(e) => vm.setSearchQ(e.target.value)}
              placeholder="输入问题或关键词（以图搜图时可留空）"
              onKeyDown={(e) => e.key === "Enter" && void vm.onSearch()}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="input-field w-auto min-w-[7rem]"
              value={vm.searchMode}
              onChange={(e) => vm.setSearchMode(e.target.value as typeof vm.searchMode)}
            >
              {(
                vm.kbMeta?.search_modes ?? [
                  { value: "default", label: "按库配置" },
                  { value: "vector", label: "纯语义" },
                  { value: "hybrid", label: "混合" },
                ]
              ).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1 text-xs text-ink-muted">
              Top
              <input
                type="number"
                min={1}
                max={50}
                className="input-field w-14"
                value={vm.searchTopK}
                onChange={(e) => vm.setSearchTopK(Number(e.target.value))}
              />
            </label>
            <button type="button" onClick={() => void vm.onSearch()} className="btn-primary" disabled={vm.searching}>
              {vm.searching ? "检索中…" : "检索"}
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-muted">
          <span className="font-medium text-ink">来源类型</span>
          {(
            vm.kbMeta?.media_types ?? [
              { value: "text", label: "文本" },
              { value: "image", label: "图片" },
              { value: "audio", label: "音频" },
              { value: "video", label: "视频" },
            ]
          ).map((o) => {
            const checked = vm.searchMediaTypes.includes(o.value);
            return (
              <label key={o.value} className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    vm.setSearchMediaTypes((prev) => (checked ? prev.filter((v) => v !== o.value) : [...prev, o.value]));
                  }}
                />
                {o.label}
              </label>
            );
          })}
          <label className="inline-flex items-center gap-2 sm:ml-2">
            <span>以图/视频搜</span>
            <select className="input-field w-auto min-w-[10rem] text-xs" value={vm.searchQueryDocId} onChange={(e) => vm.setSearchQueryDocId(e.target.value)}>
              <option value="">不选</option>
              {(vm.searchVisual ? vm.imageDocs : vm.imageVideoDocs).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                </option>
              ))}
            </select>
          </label>
          {kb.visual_embedding_model_config_id ? (
            <label className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2 py-1">
              <input
                type="checkbox"
                checked={vm.searchVisual}
                onChange={(e) => {
                  vm.setSearchVisual(e.target.checked);
                  if (e.target.checked && vm.searchMediaTypes.length === 0) {
                    vm.setSearchMediaTypes(["image"]);
                  }
                }}
              />
              CLIP 视觉相似度
            </label>
          ) : null}
        </div>
      </div>
      {vm.searchResultMode ? (
        <p className="mt-3 text-xs text-ink-faint">
          模式 <span className="font-medium text-ink">{vm.searchResultMode}</span>
          {vm.searchHits.length === 0 ? " · 无命中" : ` · ${vm.searchHits.length} 条结果`}
        </p>
      ) : null}
      <ul className="mt-4 space-y-3">
        {vm.searchHits.length === 0 && vm.searchResultMode ? (
          <li className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
            无命中结果，可调整问法或切换混合检索后重试
          </li>
        ) : null}
        {vm.searchHits.map((h, i) => (
          <li key={i} className="rounded-lg border border-line bg-surface-muted/40 p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
              <span className="rounded bg-surface px-1.5 py-0.5 font-mono text-ink">#{i + 1}</span>
              <span className="font-mono font-medium text-brand">{h.score.toFixed(3)}</span>
              {h.score_rerank != null ? <span>重排 {h.score_rerank.toFixed(3)}</span> : null}
              {h.score_vector != null ? <span>向量 {h.score_vector.toFixed(2)}</span> : null}
              {h.score_keyword != null ? <span>关键词 {h.score_keyword.toFixed(2)}</span> : null}
              {h.filename ? <span className="truncate">· {h.filename}</span> : null}
              {h.vector_type ? <span className="rounded bg-brand/10 px-1.5 py-0.5 text-brand">{h.vector_type}</span> : null}
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{h.content}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
