"use client";

import { ModelFilterChip } from "@/features/models/components/model-page-ui";
import type { ModelsPageVm } from "@/features/models/hooks/use-models-page";

export function ModelFilterPanel({ vm }: { vm: ModelsPageVm }) {
  return (
    <section className="mb-6 rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-ink">模型分类</h2>
      <div className="mb-3">
        <p className="mb-2 text-xs text-ink-muted">服务商</p>
        <div className="flex flex-wrap gap-2">
          <ModelFilterChip active={!vm.vendor} onClick={() => vm.setVendor("")}>
            全部
          </ModelFilterChip>
          {vm.vendors.map((v) => (
            <ModelFilterChip key={v.value} active={vm.vendor === v.value} onClick={() => vm.setVendor(v.value)}>
              {v.label}
            </ModelFilterChip>
          ))}
        </div>
      </div>
      <div className="mb-3">
        <p className="mb-2 text-xs text-ink-muted">类型</p>
        <div className="flex flex-wrap gap-2">
          <ModelFilterChip active={!vm.modelType} onClick={() => vm.setModelType("")}>
            全部
          </ModelFilterChip>
          {(vm.meta?.model_types ?? []).map((t) => (
            <ModelFilterChip key={t.value} active={vm.modelType === t.value} onClick={() => vm.setModelType(t.value)}>
              {t.label}
            </ModelFilterChip>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-2 text-xs text-ink-muted">来源</p>
        <div className="flex flex-wrap gap-2">
          <ModelFilterChip active={!vm.source} onClick={() => vm.setSource("")}>
            全部
          </ModelFilterChip>
          <ModelFilterChip active={vm.source === "builtin"} onClick={() => vm.setSource("builtin")}>
            内置模型
          </ModelFilterChip>
          <ModelFilterChip active={vm.source === "custom"} onClick={() => vm.setSource("custom")}>
            自定义模型
          </ModelFilterChip>
        </div>
      </div>
      <div className="mt-4">
        <input
          className="input-field w-full max-w-md"
          placeholder="搜索模型名称或编码"
          value={vm.search}
          onChange={(e) => vm.setSearch(e.target.value)}
        />
      </div>
    </section>
  );
}
