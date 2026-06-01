"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { PackDetailDialog } from "@/features/service-template-market/components/PackDetailDialog";
import type { ServiceTemplateMarketPageVm } from "@/features/service-template-market/hooks/use-service-template-market-page";
import type { BizServiceLineTemplatePack } from "@/lib/types";

const PUBLISHER_LABELS: Record<string, string> = {
  platform: "平台官方",
  partner: "合作伙伴",
  tenant: "租户分享",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已上架",
  rejected: "已驳回",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-surface-muted text-ink-muted",
  pending_review: "bg-amber-50 text-amber-700",
  published: "bg-emerald-50 text-emerald-700",
  rejected: "bg-red-50 text-red-600",
};

export function ServiceTemplateMarketPageView({ vm }: { vm: ServiceTemplateMarketPageVm }) {
  const {
    ready,
    tab,
    setTab,
    items,
    mineItems,
    templates,
    loading,
    mineLoading,
    search,
    setSearch,
    category,
    setCategory,
    customerType,
    setCustomerType,
    categoryTabs,
    industries,
    serviceLine,
    setServiceLine,
    featuredOnly,
    setFeaturedOnly,
    serviceLineOptions,
    canWriteProject,
    applyingId,
    applyPack,
    busyMineId,
    submitMine,
    withdrawMine,
    msg,
    setMsg,
    detailId,
    setDetailId,
    detailPack,
    publishOpen,
    setPublishOpen,
    openPublish,
    publishServiceLine,
    onPublishServiceLineChange,
    publishCategory,
    setPublishCategory,
    publishTags,
    togglePublishTag,
    categories,
    publishName,
    setPublishName,
    publishDesc,
    setPublishDesc,
    publishing,
    createPublish,
    openEdit,
    saveEdit,
    unpublishMine,
    editPack,
    setEditPack,
    editName,
    setEditName,
    editDesc,
    setEditDesc,
    editCategory,
    setEditCategory,
    editTags,
    toggleEditTag,
    editStageText,
    setEditStageText,
    editChatHint,
    setEditChatHint,
    editSaving,
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
        subtitle="浏览官方与租户分享的流水线方案；可将本租户配置发布供他人使用"
        actions={
          <div className="flex gap-3">
            {canWriteProject && (
              <button type="button" className="btn-primary text-xs" onClick={openPublish}>
                发布模板
              </button>
            )}
            <Link href="/business/service-templates" className="text-xs text-brand hover:underline self-center">
              我的服务线模板 →
            </Link>
          </div>
        }
      />

      <div className="mb-4 flex gap-2 border-b border-line">
        {(["plaza", "mine"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`border-b-2 px-3 py-2 text-sm transition ${
              tab === t ? "border-brand font-medium text-brand" : "border-transparent text-ink-muted hover:text-ink"
            }`}
            onClick={() => setTab(t)}
          >
            {t === "plaza" ? "模板广场" : `我的发布${mineItems.length ? ` (${mineItems.length})` : ""}`}
          </button>
        ))}
      </div>

      {msg && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <div className="flex items-start justify-between gap-2">
            <span>{msg}</span>
            <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={() => setMsg("")}>关闭</button>
          </div>
        </div>
      )}

      {tab === "plaza" ? (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            {categoryTabs.map((c) => (
              <button
                key={c.key || "all"}
                type="button"
                className={`rounded-full px-3 py-1 text-xs transition ${
                  category === c.key
                    ? "bg-brand text-white"
                    : "border border-line bg-surface text-ink-muted hover:border-brand/40 hover:text-ink"
                }`}
                onClick={() => setCategory(c.key)}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-muted">客户类型</span>
            <button
              type="button"
              className={`rounded-full px-2.5 py-0.5 text-xs ${
                !customerType ? "bg-surface-muted font-medium text-ink" : "text-ink-muted hover:text-ink"
              }`}
              onClick={() => setCustomerType("")}
            >
              全部
            </button>
            {industries.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`rounded-full px-2.5 py-0.5 text-xs ${
                  customerType === item.key
                    ? "bg-brand/10 font-medium text-brand"
                    : "border border-line text-ink-muted hover:border-brand/40 hover:text-ink"
                }`}
                onClick={() => setCustomerType(customerType === item.key ? "" : item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>

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
              <option value="">全部适用服务线</option>
              {serviceLineOptions.map((sl) => (
                <option key={sl.key} value={sl.key}>{sl.label}</option>
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
        </>
      ) : (
        <>
          {mineLoading ? (
            <p className="text-sm text-ink-muted">加载中…</p>
          ) : mineItems.length === 0 ? (
            <p className="text-sm text-ink-faint">
              暂无发布记录。在「服务线模板」页配置好阶段后，点击「发布模板」提交审核。
            </p>
          ) : (
            <div className="space-y-3">
              {mineItems.map((pack) => (
                <MineRow
                  key={pack.id}
                  pack={pack}
                  busy={busyMineId === pack.id}
                  canWrite={canWriteProject}
                  onDetail={() => setDetailId(pack.id)}
                  onEdit={() => openEdit(pack)}
                  onSubmit={() => void submitMine(pack)}
                  onWithdraw={() => void withdrawMine(pack)}
                  onUnpublish={() => void unpublishMine(pack)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <PackDetailDialog
        open={Boolean(detailPack)}
        pack={detailPack}
        applying={detailPack ? applyingId === detailPack.id : false}
        canApply={canWriteProject && tab === "plaza"}
        onClose={() => setDetailId(null)}
        onApply={() => detailPack && void applyPack(detailPack)}
      />

      {publishOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setPublishOpen(false)}>
          <div className="card w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ink">发布到模板市场</h2>
            <p className="mt-1 text-xs text-ink-muted">将当前租户某条服务线的阶段与 AI 配置打包为草稿，提交后由平台审核上架。</p>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="text-xs text-ink-muted">适用服务线</span>
                <select
                  className="input-field mt-1 w-full text-sm"
                  value={publishServiceLine}
                  onChange={(e) => onPublishServiceLineChange(e.target.value)}
                >
                  {templates.map((t) => (
                    <option key={t.service_line} value={t.service_line}>
                      {t.label}{t.stages.length === 0 ? "（无阶段）" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">场景分类</span>
                <select
                  className="input-field mt-1 w-full text-sm"
                  value={publishCategory}
                  onChange={(e) => setPublishCategory(e.target.value)}
                >
                  {categories.map((c) => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
              </label>
              <fieldset>
                <legend className="text-xs text-ink-muted">客户类型（可多选）</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {industries.map((item) => (
                    <label key={item.key} className="flex cursor-pointer items-center gap-1.5 text-xs text-ink">
                      <input
                        type="checkbox"
                        checked={publishTags.includes(item.key)}
                        onChange={() => togglePublishTag(item.key)}
                      />
                      {item.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="block">
                <span className="text-xs text-ink-muted">模板名称</span>
                <input className="input-field mt-1 w-full text-sm" value={publishName} onChange={(e) => setPublishName(e.target.value)} placeholder="如：政府活动精简版" />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">简介</span>
                <textarea className="input-field mt-1 w-full text-sm" rows={2} value={publishDesc} onChange={(e) => setPublishDesc(e.target.value)} />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn-ghost text-sm" onClick={() => setPublishOpen(false)}>取消</button>
              <button type="button" className="btn-primary text-sm" disabled={publishing || !publishName.trim()} onClick={() => void createPublish()}>
                {publishing ? "创建中…" : "创建草稿"}
              </button>
            </div>
          </div>
        </div>
      )}

      {editPack && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setEditPack(null)}>
          <div className="card max-h-[85vh] w-full max-w-lg overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ink">编辑模板包</h2>
            <p className="mt-1 text-xs text-ink-muted">
              {editPack.category_label} · 适用于 {editPack.service_line_label} · {editPack.status === "rejected" ? "已驳回，修改后可重新提交" : "草稿"}
            </p>
            {editPack.review_note && editPack.status === "rejected" && (
              <p className="mt-2 text-xs text-red-600">驳回原因：{editPack.review_note}</p>
            )}
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="text-xs text-ink-muted">名称</span>
                <input className="input-field mt-1 w-full text-sm" value={editName} onChange={(e) => setEditName(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">简介</span>
                <textarea className="input-field mt-1 w-full text-sm" rows={2} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">场景分类</span>
                <select className="input-field mt-1 w-full text-sm" value={editCategory} onChange={(e) => setEditCategory(e.target.value)}>
                  {categories.map((c) => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
              </label>
              <fieldset>
                <legend className="text-xs text-ink-muted">客户类型（可多选）</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {industries.map((item) => (
                    <label key={item.key} className="flex cursor-pointer items-center gap-1.5 text-xs text-ink">
                      <input
                        type="checkbox"
                        checked={editTags.includes(item.key)}
                        onChange={() => toggleEditTag(item.key)}
                      />
                      {item.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="block">
                <span className="text-xs text-ink-muted">阶段（每行一个）</span>
                <textarea className="input-field mt-1 w-full font-mono text-sm" rows={6} value={editStageText} onChange={(e) => setEditStageText(e.target.value)} />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">AI 对话提示</span>
                <textarea className="input-field mt-1 w-full text-sm" rows={2} value={editChatHint} onChange={(e) => setEditChatHint(e.target.value)} />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn-ghost text-sm" onClick={() => setEditPack(null)}>取消</button>
              <button type="button" className="btn-primary text-sm" disabled={editSaving || !editName.trim()} onClick={() => void saveEdit()}>
                {editSaving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MineRow({
  pack,
  busy,
  canWrite,
  onDetail,
  onEdit,
  onSubmit,
  onWithdraw,
  onUnpublish,
}: {
  pack: BizServiceLineTemplatePack;
  busy: boolean;
  canWrite: boolean;
  onDetail: () => void;
  onEdit: () => void;
  onSubmit: () => void;
  onWithdraw: () => void;
  onUnpublish: () => void;
}) {
  const status = pack.status ?? "draft";
  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">{pack.category_label}</span>
          <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLORS[status] ?? STATUS_COLORS.draft}`}>
            {STATUS_LABELS[status] ?? status}
          </span>
          {status === "published" && pack.is_active === false && (
            <span className="rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">已下架</span>
          )}
        </div>
        <p className="mt-1 font-medium text-ink">{pack.name}</p>
        <p className="mt-0.5 text-xs text-ink-faint">适用于 {pack.service_line_label}</p>
        {pack.review_note && status === "rejected" && (
          <p className="mt-1 text-xs text-red-600">驳回原因：{pack.review_note}</p>
        )}
        {status === "published" && pack.install_count > 0 && (
          <p className="mt-1 text-xs text-ink-faint">{pack.install_count} 次被其他租户应用</p>
        )}
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        <button type="button" className="text-brand hover:underline" onClick={onDetail}>详情</button>
        {canWrite && (status === "draft" || status === "rejected") && (
          <>
            <button type="button" className="text-brand hover:underline" onClick={onEdit}>编辑</button>
            <button type="button" className="text-brand hover:underline disabled:opacity-50" disabled={busy} onClick={onSubmit}>
              {busy ? "…" : "提交审核"}
            </button>
            <button type="button" className="text-ink-muted hover:underline disabled:opacity-50" disabled={busy} onClick={onWithdraw}>删除</button>
          </>
        )}
        {canWrite && status === "published" && pack.is_active !== false && (
          <button type="button" className="text-ink-muted hover:underline disabled:opacity-50" disabled={busy} onClick={onUnpublish}>下架</button>
        )}
      </div>
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
          <p className="text-xs text-ink-muted">{pack.category_label}</p>
          <h2 className="mt-0.5 text-sm font-semibold text-ink">{pack.name}</h2>
          <p className="mt-0.5 text-xs text-ink-faint">适用于 {pack.service_line_label}</p>
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
        {(pack.tag_labels.length ? pack.tag_labels : pack.tags).map((tag, i) => (
          <span key={`${pack.id}-tag-${i}`} className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-muted">{tag}</span>
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
