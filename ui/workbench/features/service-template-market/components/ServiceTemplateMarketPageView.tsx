"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { PackDetailDialog } from "@/features/service-template-market/components/PackDetailDialog";
import type { ServiceTemplateMarketPageVm } from "@/features/service-template-market/hooks/use-service-template-market-page";
import {
  PACK_PUBLISHER_LABELS,
  PACK_STATUS_COLORS,
  PACK_STATUS_LABELS,
} from "@/features/service-template-market/lib/template-pack-labels";
import { StatChip } from "@/components/ui/StatChip";
import type { BizServiceLineTemplatePack } from "@/lib/types";

function TabToggle({ tab, mineCount, onChange }: { tab: "plaza" | "mine"; mineCount: number; onChange: (t: "plaza" | "mine") => void }) {
  return (
    <div className="flex rounded-lg border border-line p-0.5 text-xs">
      <button
        type="button"
        className={`rounded-md px-3 py-1.5 ${tab === "plaza" ? "bg-brand text-white" : "text-ink-muted hover:text-ink"}`}
        onClick={() => onChange("plaza")}
      >
        模板广场
      </button>
      <button
        type="button"
        className={`rounded-md px-3 py-1.5 ${tab === "mine" ? "bg-brand text-white" : "text-ink-muted hover:text-ink"}`}
        onClick={() => onChange("mine")}
      >
        我的发布{mineCount > 0 ? ` (${mineCount})` : ""}
      </button>
    </div>
  );
}

function GridSkeleton() {
  return (
    <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="h-52 animate-pulse rounded-xl bg-surface-muted" />
      ))}
    </div>
  );
}

function PlazaFilters({ vm }: { vm: ServiceTemplateMarketPageVm }) {
  const {
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
    clearFilters,
    hasActiveFilters,
  } = vm;

  return (
    <div className="space-y-3 border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          className="input-field h-9 w-full max-w-xs text-sm"
          placeholder="搜索模板名称或描述…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs transition ${
            featuredOnly
              ? "bg-amber-50 font-medium text-amber-800 ring-1 ring-amber-200"
              : "border border-line bg-surface text-ink-muted hover:border-amber-200 hover:text-ink"
          }`}
          onClick={() => setFeaturedOnly(!featuredOnly)}
        >
          仅精选
        </button>
        {hasActiveFilters ? (
          <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">场景</span>
        {categoryTabs.map((c) => (
          <button
            key={c.key || "all"}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              category === c.key
                ? "bg-brand text-white"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => setCategory(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">客户类型</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !customerType ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
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
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => setCustomerType(customerType === item.key ? "" : item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">服务线</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !serviceLine ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
          }`}
          onClick={() => setServiceLine("")}
        >
          全部
        </button>
        {serviceLineOptions.map((sl) => (
          <button
            key={sl.key}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              serviceLine === sl.key
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => setServiceLine(serviceLine === sl.key ? "" : sl.key)}
          >
            {sl.label}
          </button>
        ))}
      </div>
    </div>
  );
}

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
    industries,
    categories,
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
    hasActiveFilters,
    filterCategoryLabel,
    filterCustomerLabel,
    filterServiceLineLabel,
    featuredOnly,
  } = vm;

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  const statValue = tab === "plaza" ? String(items.length) : String(mineItems.length);
  const statHint =
    tab === "plaza"
      ? hasActiveFilters
        ? "当前筛选结果"
        : featuredOnly
          ? "仅精选模板"
          : "广场可见模板"
      : "草稿与已发布";

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        flowHighlight={false}
        compact
        title="模板市场"
        subtitle="浏览官方与租户分享的流水线方案；可将本租户配置发布供他人使用"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <TabToggle tab={tab} mineCount={mineItems.length} onChange={setTab} />
            {canWriteProject ? (
              <button type="button" className="btn-primary text-sm" onClick={openPublish}>
                发布模板
              </button>
            ) : null}
            <Link href="/business/service-templates" className="btn-ghost text-xs">
              服务线模板
            </Link>
          </div>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip label={tab === "plaza" ? "匹配模板" : "我的发布"} value={statValue} hint={statHint} />
        <StatChip
          label="场景分类"
          value={tab === "plaza" ? filterCategoryLabel : tab === "mine" ? "我的发布" : "—"}
          hint={tab === "plaza" ? "主分类维度" : "审核与上下架"}
        />
        <StatChip
          label="筛选维度"
          value={tab === "plaza" ? (hasActiveFilters ? "已筛选" : "全部") : `${mineItems.filter((p) => p.status === "published").length} 已上架`}
          hint={
            tab === "plaza"
              ? `${filterCustomerLabel} · ${filterServiceLineLabel}`
              : "草稿可编辑后提交"
          }
        />
      </div>

      {msg ? (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <div className="flex items-start justify-between gap-2">
            <span>{msg}</span>
            <button type="button" className="shrink-0 text-xs opacity-70 hover:opacity-100" onClick={() => setMsg("")}>
              关闭
            </button>
          </div>
        </div>
      ) : null}

      {tab === "plaza" ? (
        <div className="card overflow-hidden">
          <PlazaFilters vm={vm} />
          {loading ? (
            <GridSkeleton />
          ) : items.length === 0 ? (
            <div className="px-4 py-16 text-center">
              <p className="text-sm text-ink-muted">暂无匹配的模板包</p>
              <p className="mt-1 text-xs text-ink-faint">调整筛选条件，或前往服务线模板页配置后发布</p>
            </div>
          ) : (
            <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
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
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="border-b border-line bg-surface-muted/30 px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">我的发布</h2>
            <p className="mt-0.5 text-xs text-ink-muted">草稿提交审核后上架；已驳回可修改后重新提交</p>
          </div>
          {mineLoading ? (
            <div className="space-y-3 p-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-muted" />
              ))}
            </div>
          ) : mineItems.length === 0 ? (
            <div className="px-4 py-16 text-center">
              <p className="text-sm text-ink-muted">暂无发布记录</p>
              <p className="mt-1 text-xs text-ink-faint">在服务线模板页配置阶段后，点击「发布模板」提交审核</p>
              {canWriteProject ? (
                <button type="button" className="btn-primary mt-4 text-sm" onClick={openPublish}>
                  发布模板
                </button>
              ) : null}
            </div>
          ) : (
            <div className="divide-y divide-line-soft">
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
        </div>
      )}

      <PackDetailDialog
        open={Boolean(detailPack)}
        pack={detailPack}
        applying={detailPack ? applyingId === detailPack.id : false}
        canApply={canWriteProject && tab === "plaza"}
        onClose={() => setDetailId(null)}
        onApply={() => detailPack && void applyPack(detailPack)}
      />

      {publishOpen ? (
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
                      {t.label}
                      {t.stages.length === 0 ? "（无阶段）" : ""}
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
                    <option key={c.key} value={c.key}>
                      {c.label}
                    </option>
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
                <input
                  className="input-field mt-1 w-full text-sm"
                  value={publishName}
                  onChange={(e) => setPublishName(e.target.value)}
                  placeholder="如：政府活动精简版"
                />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">简介</span>
                <textarea className="input-field mt-1 w-full text-sm" rows={2} value={publishDesc} onChange={(e) => setPublishDesc(e.target.value)} />
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="btn-ghost text-sm" onClick={() => setPublishOpen(false)}>
                取消
              </button>
              <button
                type="button"
                className="btn-primary text-sm"
                disabled={publishing || !publishName.trim()}
                onClick={() => void createPublish()}
              >
                {publishing ? "创建中…" : "创建草稿"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {editPack ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setEditPack(null)}>
          <div className="card max-h-[85vh] w-full max-w-lg overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ink">编辑模板包</h2>
            <p className="mt-1 text-xs text-ink-muted">
              {editPack.category_label} · 适用于 {editPack.service_line_label} ·{" "}
              {editPack.status === "rejected" ? "已驳回，修改后可重新提交" : "草稿"}
            </p>
            {editPack.review_note && editPack.status === "rejected" ? (
              <p className="mt-2 text-xs text-red-600">驳回原因：{editPack.review_note}</p>
            ) : null}
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
                    <option key={c.key} value={c.key}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset>
                <legend className="text-xs text-ink-muted">客户类型（可多选）</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {industries.map((item) => (
                    <label key={item.key} className="flex cursor-pointer items-center gap-1.5 text-xs text-ink">
                      <input type="checkbox" checked={editTags.includes(item.key)} onChange={() => toggleEditTag(item.key)} />
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
              <button type="button" className="btn-ghost text-sm" onClick={() => setEditPack(null)}>
                取消
              </button>
              <button type="button" className="btn-primary text-sm" disabled={editSaving || !editName.trim()} onClick={() => void saveEdit()}>
                {editSaving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
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
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 transition hover:bg-surface-muted/30">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">{pack.category_label}</span>
          <span className={`rounded-full px-2 py-0.5 text-xs ${PACK_STATUS_COLORS[status] ?? PACK_STATUS_COLORS.draft}`}>
            {PACK_STATUS_LABELS[status] ?? status}
          </span>
          {status === "published" && pack.is_active === false ? (
            <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">已下架</span>
          ) : null}
        </div>
        <p className="mt-1 font-medium text-ink">{pack.name}</p>
        <p className="mt-0.5 text-xs text-ink-faint">适用于 {pack.service_line_label}</p>
        {pack.review_note && status === "rejected" ? (
          <p className="mt-1 text-xs text-red-600">驳回原因：{pack.review_note}</p>
        ) : null}
        {status === "published" && pack.install_count > 0 ? (
          <p className="mt-1 text-xs text-ink-faint">{pack.install_count} 次被其他租户应用</p>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        <button type="button" className="text-brand hover:underline" onClick={onDetail}>
          详情
        </button>
        {canWrite && (status === "draft" || status === "rejected") ? (
          <>
            <button type="button" className="text-brand hover:underline" onClick={onEdit}>
              编辑
            </button>
            <button type="button" className="text-brand hover:underline disabled:opacity-50" disabled={busy} onClick={onSubmit}>
              {busy ? "…" : "提交审核"}
            </button>
            <button type="button" className="text-ink-muted hover:underline disabled:opacity-50" disabled={busy} onClick={onWithdraw}>
              删除
            </button>
          </>
        ) : null}
        {canWrite && status === "published" && pack.is_active !== false ? (
          <button type="button" className="text-ink-muted hover:underline disabled:opacity-50" disabled={busy} onClick={onUnpublish}>
            下架
          </button>
        ) : null}
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
    <article className="flex flex-col rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/25 hover:shadow-panel">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-ink-muted">{pack.category_label}</p>
          <h2 className="mt-0.5 truncate text-sm font-semibold text-ink">{pack.name}</h2>
          <p className="mt-0.5 text-xs text-ink-faint">适用于 {pack.service_line_label}</p>
        </div>
        {pack.is_featured ? (
          <span className="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700">精选</span>
        ) : null}
      </div>
      {pack.description ? <p className="mt-2 line-clamp-2 text-xs text-ink-muted">{pack.description}</p> : null}
      <ol className="mt-3 flex flex-wrap gap-1">
        {pack.stages.slice(0, 5).map((s, i) => (
          <li key={`${pack.id}-${i}`} className="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-ink">
            {i + 1}. {s}
          </li>
        ))}
        {pack.stages.length > 5 ? <li className="text-xs text-ink-faint">+{pack.stages.length - 5}</li> : null}
      </ol>
      <div className="mt-3 flex flex-wrap gap-1">
        {(pack.tag_labels.length ? pack.tag_labels : pack.tags).map((tag, i) => (
          <span key={`${pack.id}-tag-${i}`} className="rounded-full border border-line px-2 py-0.5 text-xs text-ink-muted">
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-end justify-between gap-2 pt-4 text-xs text-ink-faint">
        <span className="min-w-0 truncate">
          {PACK_PUBLISHER_LABELS[pack.publisher_type] ?? pack.publisher_type} · {pack.publisher_name}
          {pack.install_count > 0 ? ` · ${pack.install_count} 次应用` : ""}
        </span>
        <div className="flex shrink-0 gap-2">
          <button type="button" className="text-brand hover:underline" onClick={onDetail}>
            详情
          </button>
          {canApply ? (
            <button type="button" className="text-brand hover:underline disabled:opacity-50" disabled={applying} onClick={onApply}>
              {applying ? "应用中…" : "应用"}
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}
