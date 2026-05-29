"use client";

import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagPicker } from "@/components/tag/TagPicker";
import { MarketplacePageMessage } from "@/features/marketplace/components/marketplace-page-ui";
import { marketplaceVisibilityLabel } from "@/features/marketplace/lib/marketplace-labels";
import type { MarketplacePageVm } from "@/features/marketplace/hooks/use-marketplace-page";

export function MarketplacePublishView({ vm }: { vm: MarketplacePageVm }) {
  return (
    <ResourceListLayout {...vm.layoutCommon} search="" onSearchChange={() => {}} showSearch={false}>
      {vm.msg ? <MarketplacePageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      <div className="col-span-full mx-auto w-full max-w-2xl">
        <section className="rounded-xl border border-line bg-surface p-6 shadow-panel">
          <h2 className="text-base font-semibold text-ink">从资源打包应用</h2>
          <p className="mt-1 text-sm text-ink-muted">选择本租户已有资源生成安装包草稿，提交审核通过后即可被其他租户安装。</p>
          <label className="mt-5 block space-y-1">
            <span className="text-xs text-ink-muted">应用名称</span>
            <input
              className="input-field w-full"
              value={vm.publishName}
              onChange={(e) => vm.setPublishName(e.target.value)}
              placeholder="例如：客服 RAG 套件"
            />
          </label>
          <label className="mt-3 block space-y-1">
            <span className="text-xs text-ink-muted">描述</span>
            <textarea
              className="input-field min-h-[88px] w-full resize-y"
              value={vm.publishDesc}
              onChange={(e) => vm.setPublishDesc(e.target.value)}
              placeholder="简要说明适用场景"
            />
          </label>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1">
              <span className="text-xs text-ink-muted">图标</span>
              <input className="input-field w-full" value={vm.publishIcon} onChange={(e) => vm.setPublishIcon(e.target.value)} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs text-ink-muted">分类</span>
              <select className="input-field w-full" value={vm.publishCategory} onChange={(e) => vm.setPublishCategory(e.target.value)}>
                {vm.categories.map((c) => (
                  <option key={c.id} value={c.slug}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="mt-3 block space-y-1">
            <span className="text-xs text-ink-muted">可见范围</span>
            <select
              className="input-field w-full"
              value={vm.publishVisibility}
              onChange={(e) => vm.setPublishVisibility(e.target.value as "public" | "tenant_only")}
            >
              <option value="public">{marketplaceVisibilityLabel("public", vm.marketplaceMeta)}</option>
              <option value="tenant_only">{marketplaceVisibilityLabel("tenant_only", vm.marketplaceMeta)}</option>
            </select>
            <p className="text-[11px] text-ink-faint">「租户内可见」审核通过后仅本租户成员可在广场浏览与安装。</p>
          </label>
          <label className="mt-4 block space-y-1">
            <span className="text-xs text-ink-muted">标签</span>
            <TagPicker value={vm.publishTagIds} onChange={vm.setPublishTagIds} />
          </label>
          <p className="mt-5 text-xs font-medium text-ink-muted">关联资源（至少一项）</p>
          <div className="mt-2 space-y-2">
            <select className="input-field w-full" value={vm.publishKbId} onChange={(e) => vm.setPublishKbId(e.target.value)}>
              <option value="">不打包知识库</option>
              {vm.resourceOptions.kbs.map((k) => (
                <option key={k.id} value={k.id}>
                  知识库 · {k.name}
                </option>
              ))}
            </select>
            <select className="input-field w-full" value={vm.publishFlowId} onChange={(e) => vm.setPublishFlowId(e.target.value)}>
              <option value="">不打包流程</option>
              {vm.resourceOptions.flows.map((f) => (
                <option key={f.id} value={f.id}>
                  流程 · {f.name}
                </option>
              ))}
            </select>
            <select className="input-field w-full" value={vm.publishAgentId} onChange={(e) => vm.setPublishAgentId(e.target.value)}>
              <option value="">不打包智能体</option>
              {vm.resourceOptions.agents.map((a) => (
                <option key={a.id} value={a.id}>
                  智能体 · {a.name}
                </option>
              ))}
            </select>
          </div>
          <button type="button" disabled={vm.publishLoading} onClick={vm.onCreateDraft} className="btn-primary mt-6 w-full">
            {vm.publishLoading ? "创建中…" : "保存为草稿"}
          </button>
        </section>
      </div>
    </ResourceListLayout>
  );
}
