"use client";

import type { TemplatePackReviewPageVm } from "@/hooks/use-template-pack-review-page";
import type { AdminTemplatePack } from "@/lib/api";

export function TemplatePackReviewPageView({ vm }: { vm: TemplatePackReviewPageVm }) {
  const {
    tab,
    setTab,
    list,
    detail,
    setDetail,
    loadDetail,
    rejectTarget,
    setRejectTarget,
    rejectNote,
    setRejectNote,
    busyId,
    rejectLoading,
    onApprove,
    onUnpublish,
    onToggleFeatured,
    onConfirmReject,
    msg,
    err,
  } = vm;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-ink">模板包审核</h1>
        <p className="mt-1 text-sm text-ink-muted">审核租户提交、管理已上架模板的下架与精选。</p>
      </header>

      <div className="flex gap-2 border-b border-line">
        {(["pending", "published"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`border-b-2 px-3 py-2 text-sm ${tab === t ? "border-brand font-medium text-brand" : "border-transparent text-ink-muted"}`}
            onClick={() => { setTab(t); setDetail(null); }}
          >
            {t === "pending" ? "待审核" : "已上架"}
          </button>
        ))}
      </div>

      {msg ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{msg}</div> : null}
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{err}</div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="text-sm font-semibold text-ink">{tab === "pending" ? "待审核" : "已上架"}</h2>
          {list.loading ? (
            <p className="mt-3 text-sm text-ink-muted">加载中…</p>
          ) : list.items.length === 0 ? (
            <p className="mt-3 text-sm text-ink-faint">暂无数据</p>
          ) : (
            <ul className="mt-3 divide-y divide-line">
              {list.items.map((item) => (
                <PackListRow
                  key={item.id}
                  item={item}
                  tab={tab}
                  busy={busyId === item.id}
                  onSelect={() => void loadDetail(item.id)}
                  onApprove={() => void onApprove(item.id)}
                  onReject={() => setRejectTarget({ id: item.id, name: item.name })}
                  onUnpublish={() => void onUnpublish(item.id)}
                  onToggleFeatured={(featured) => void onToggleFeatured(item.id, featured)}
                />
              ))}
            </ul>
          )}
          {!list.loading && list.total > list.size && (
            <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
              <span>共 {list.total} 条</span>
              <div className="flex gap-2">
                <button type="button" className="disabled:opacity-40" disabled={list.page <= 1} onClick={() => list.setPage(list.page - 1)}>上一页</button>
                <span>{list.page}</span>
                <button type="button" className="disabled:opacity-40" disabled={list.page * list.size >= list.total} onClick={() => list.setPage(list.page + 1)}>下一页</button>
              </div>
            </div>
          )}
        </section>

        <section className="card p-4">
          <h2 className="text-sm font-semibold text-ink">详情</h2>
          {!detail ? (
            <p className="mt-3 text-sm text-ink-faint">点击左侧条目查看</p>
          ) : (
            <PackDetailPanel
              detail={detail}
              tab={tab}
              busy={busyId === detail.id}
              onApprove={() => void onApprove(detail.id)}
              onReject={() => setRejectTarget({ id: detail.id, name: detail.name })}
              onUnpublish={() => void onUnpublish(detail.id)}
              onToggleFeatured={(featured) => void onToggleFeatured(detail.id, featured)}
            />
          )}
        </section>
      </div>

      {rejectTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card w-full max-w-md p-5">
            <h3 className="font-semibold text-ink">驳回「{rejectTarget.name}」</h3>
            <textarea
              className="input-field mt-3 w-full text-sm"
              rows={3}
              placeholder="驳回原因（将展示给租户）"
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-ghost text-sm" onClick={() => { setRejectTarget(null); setRejectNote(""); }}>取消</button>
              <button type="button" className="btn-primary text-sm bg-red-600 hover:bg-red-700" disabled={rejectLoading} onClick={() => void onConfirmReject()}>
                {rejectLoading ? "提交中…" : "确认驳回"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PackListRow({
  item,
  tab,
  busy,
  onSelect,
  onApprove,
  onReject,
  onUnpublish,
  onToggleFeatured,
}: {
  item: AdminTemplatePack;
  tab: "pending" | "published";
  busy: boolean;
  onSelect: () => void;
  onApprove: () => void;
  onReject: () => void;
  onUnpublish: () => void;
  onToggleFeatured: (featured: boolean) => void;
}) {
  return (
    <li className="flex items-center justify-between gap-2 py-3">
      <button type="button" className="min-w-0 text-left" onClick={onSelect}>
        <p className="truncate text-sm font-medium text-ink">
          {item.name}
          {item.is_featured && tab === "published" ? <span className="ml-2 text-xs text-amber-600">精选</span> : null}
          {tab === "published" && !item.is_active ? <span className="ml-2 text-xs text-ink-muted">已下架</span> : null}
        </p>
        <p className="text-xs text-ink-muted">{item.service_line_label} · {item.publisher_name}</p>
      </button>
      <div className="flex shrink-0 flex-wrap justify-end gap-2">
        {tab === "pending" ? (
          <>
            <button type="button" className="text-xs text-brand hover:underline disabled:opacity-50" disabled={busy} onClick={onApprove}>通过</button>
            <button type="button" className="text-xs text-red-600 hover:underline" onClick={onReject}>驳回</button>
          </>
        ) : (
          <>
            {item.is_active && (
              <button type="button" className="text-xs text-brand hover:underline disabled:opacity-50" disabled={busy} onClick={() => onToggleFeatured(!item.is_featured)}>
                {item.is_featured ? "取消精选" : "设为精选"}
              </button>
            )}
            {item.is_active && (
              <button type="button" className="text-xs text-ink-muted hover:underline disabled:opacity-50" disabled={busy} onClick={onUnpublish}>下架</button>
            )}
          </>
        )}
      </div>
    </li>
  );
}

function PackDetailPanel({
  detail,
  tab,
  busy,
  onApprove,
  onReject,
  onUnpublish,
  onToggleFeatured,
}: {
  detail: AdminTemplatePack;
  tab: "pending" | "published";
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onUnpublish: () => void;
  onToggleFeatured: (featured: boolean) => void;
}) {
  return (
    <div className="mt-3 space-y-3 text-sm">
      <p><span className="text-ink-muted">服务线：</span>{detail.service_line_label}</p>
      <p><span className="text-ink-muted">发布方：</span>{detail.publisher_name}</p>
      {detail.description && <p className="text-ink-muted">{detail.description}</p>}
      <div>
        <p className="font-medium text-ink">阶段</p>
        <ol className="mt-1 list-decimal pl-5 text-ink-muted">
          {detail.stages.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      </div>
      <div className="flex flex-wrap gap-2 pt-2">
        {tab === "pending" && (
          <>
            <button type="button" className="btn-primary text-xs" disabled={busy} onClick={onApprove}>通过上架</button>
            <button type="button" className="btn-ghost text-xs text-red-600" onClick={onReject}>驳回</button>
          </>
        )}
        {tab === "published" && detail.is_active && (
          <>
            <button type="button" className="btn-primary text-xs" disabled={busy} onClick={() => onToggleFeatured(!detail.is_featured)}>
              {detail.is_featured ? "取消精选" : "设为精选"}
            </button>
            <button type="button" className="btn-ghost text-xs" disabled={busy} onClick={onUnpublish}>下架</button>
          </>
        )}
      </div>
    </div>
  );
}
