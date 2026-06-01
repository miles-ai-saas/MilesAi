"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import type { ServiceTemplateMarketPageVm } from "@/features/service-template-market/hooks/use-service-template-market-page";
import type { BizServiceLineTemplatePack } from "@/lib/types";

const PUBLISHER_LABELS: Record<string, string> = {
  platform: "平台官方",
  partner: "合作伙伴",
};

export function ServiceTemplateMarketPageView({ vm }: { vm: ServiceTemplateMarketPageVm }) {
  const {
    ready,
    items,
    loading,
    search,
    setSearch,
    serviceLine,
    setServiceLine,
    featuredOnly,
    setFeaturedOnly,
    serviceLineOptions,
    canWriteProject,
    applyingId,
    applyPack,
    msg,
    setMsg,
    detailId,
    setDetailId,
    detailPack,
  } = vm;

  if (!ready) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        compact
        title="模板市场"
        subtitle="浏览平台与合作伙伴发布的服务线流水线方案，一键应用到租户配置"
        actions={
          <Link href="/business/service-templates" className="text-xs text-brand hover:underline">
            我的服务线模板 →
          </Link>
        }
      />

      {msg && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <div className="flex items-start justify-between gap-2">
            <span>{msg}</span>
            <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={() => setMsg("")}>关闭</button>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="search"
          className="input-field h-9 w-full max-w-xs text-sm"
          placeholder="搜索模板名称或描述"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-ink-muted">
          <input type="checkbox" checked={featuredOnly} onChange={(e) => setFeaturedOnly(e.target.checked)} />
          仅精选
        </label>
        <select
          className="input-field h-9 w-auto text-sm"
          value={serviceLine}
          onChange={(e) => setServiceLine(e.target.value)}
        >
          <option value="">全部服务线</option>
          {serviceLineOptions.map(([sl, label]) => (
            <option key={sl} value={sl}>{label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-ink-muted">加载模板…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-ink-faint">暂无匹配的模板包</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((pack) => (
            <PackCard
              key={pack.id}
              pack={pack}
              applying={applyingId === pack.id}
              canApply={canWriteProject}
              onDetail={() => setDetailId(pack.id)}
              onApply={() => void applyPack(pack)}
            />
          ))}
        </div>
      )}

      {detailPack && (
        <PackDetailDialog
          pack={detailPack}
          applying={applyingId === detailPack.id}
          canApply={canWriteProject}
          onClose={() => setDetailId(null)}
          onApply={() => void applyPack(detailPack)}
        />
      )}
    </div>
  );
}

function PackCard({
  pack,
  applying,
  canApply,
  onDetail,
  onApply,
}: {
  pack: BizServiceLineTemplatePack;
  applying: boolean;
  canApply: boolean;
  onDetail: () => void;
  onApply: () => void;
}) {
  return (
    <div className="card flex flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs text-ink-muted">{pack.service_line_label}</p>
          <h2 className="mt-0.5 text-sm font-semibold text-ink">{pack.name}</h2>
        </div>
        {pack.is_featured && (
          <span className="shrink-0 rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">精选</span>
        )}
      </div>
      {pack.description && (
        <p className="mt-2 line-clamp-2 text-xs text-ink-muted">{pack.description}</p>
      )}
      <ol className="mt-3 flex flex-wrap gap-1">
        {pack.stages.slice(0, 5).map((s, i) => (
          <li key={`${pack.id}-${i}`} className="rounded bg-surface-muted px-1.5 py-0.5 text-xs text-ink">
            {i + 1}. {s}
          </li>
        ))}
        {pack.stages.length > 5 && (
          <li className="text-xs text-ink-faint">+{pack.stages.length - 5}</li>
        )}
      </ol>
      <div className="mt-3 flex flex-wrap gap-1">
        {pack.tags.map((tag) => (
          <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-muted">{tag}</span>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between pt-4 text-xs text-ink-faint">
        <span>
          {PUBLISHER_LABELS[pack.publisher_type] ?? pack.publisher_type} · {pack.publisher_name}
          {pack.install_count > 0 ? ` · ${pack.install_count} 次应用` : ""}
        </span>
        <div className="flex gap-2">
          <button type="button" className="text-brand hover:underline" onClick={onDetail}>详情</button>
          {canApply && (
            <button
              type="button"
              className="text-brand hover:underline disabled:opacity-50"
              disabled={applying}
              onClick={onApply}
            >
              {applying ? "应用中…" : "应用"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function PackDetailDialog({
  pack,
  applying,
  canApply,
  onClose,
  onApply,
}: {
  pack: BizServiceLineTemplatePack;
  applying: boolean;
  canApply: boolean;
  onClose: () => void;
  onApply: () => void;
}) {
  const ai = pack.ai_config ?? {};
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="card max-h-[85vh] w-full max-w-lg overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-ink-muted">{pack.service_line_label}</p>
            <h2 className="text-lg font-semibold text-ink">{pack.name}</h2>
            <p className="mt-1 text-xs text-ink-faint">
              {PUBLISHER_LABELS[pack.publisher_type] ?? pack.publisher_type} · {pack.publisher_name}
            </p>
          </div>
          <button type="button" className="text-ink-muted hover:text-ink" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        {pack.description && <p className="mt-3 text-sm text-ink-muted">{pack.description}</p>}

        <section className="mt-4">
          <h3 className="text-xs font-medium text-ink">阶段流水线</h3>
          <ol className="mt-2 space-y-1">
            {pack.stages.map((s, i) => (
              <li key={i} className="text-sm text-ink">{i + 1}. {s}</li>
            ))}
          </ol>
        </section>

        {(ai.agent_tag || ai.chat_hint || (ai.quick_prompts?.length ?? 0) > 0) && (
          <section className="mt-4 rounded-lg bg-surface-muted/60 p-3">
            <h3 className="text-xs font-medium text-ink">AI 推荐配置</h3>
            {ai.agent_tag && <p className="mt-1 text-xs text-ink-muted">智能体标签：{ai.agent_tag}</p>}
            {ai.chat_hint && <p className="mt-1 text-xs text-ink-muted">对话提示：{ai.chat_hint}</p>}
            {(ai.quick_prompts?.length ?? 0) > 0 && (
              <p className="mt-1 text-xs text-ink-muted">快捷提示：{ai.quick_prompts!.join(" · ")}</p>
            )}
          </section>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-ghost text-sm" onClick={onClose}>关闭</button>
          {canApply && (
            <button type="button" className="btn-primary text-sm" disabled={applying} onClick={onApply}>
              {applying ? "应用中…" : "应用到我的租户"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
