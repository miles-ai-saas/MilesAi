"use client";

/** 应用市场详情：右侧抽屉（链路 §12）。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { MarketplaceStarDisplay } from "@/features/marketplace/components/MarketplaceAppCardParts";
import { TagChips } from "@/components/tag/TagChips";
import { marketplaceStatusLabel } from "@/features/marketplace/lib/marketplace-labels";
import type { MarketplaceMeta } from "@/lib/types";
import type { AppRating, MarketplaceApp, MarketplaceAppDetail } from "@/lib/types";

function manifestResourceItems(manifest: Record<string, unknown>) {
  const resourceLabels: Record<string, string> = {
    knowledge_base: "知识库",
    flow: "流程",
    agent: "智能体",
  };
  const resources = (manifest.resources ?? manifest) as Record<string, unknown>;
  const items: { key: string; label: string; name: string; hint?: string }[] = [];

  for (const key of ["knowledge_base", "flow", "agent"] as const) {
    const raw = resources[key];
    if (!raw || typeof raw !== "object") continue;
    const obj = raw as Record<string, unknown>;
    const name = String(obj.name ?? "—");
    let hint: string | undefined;
    if (key === "agent") {
      const parts: string[] = [];
      if (obj.bind_kb) parts.push("绑知识库");
      if (obj.bind_flow) parts.push("绑流程");
      if (parts.length) hint = parts.join(" · ");
    }
    if (key === "flow" && obj.auto_publish === false) {
      hint = hint ? `${hint} · 安装后不自动发布` : "安装后不自动发布";
    }
    items.push({
      key,
      label: resourceLabels[key] ?? key,
      name,
      hint,
    });
  }

  return items;
}

function DetailSection({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface-muted/30 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}

type Props = {
  open: boolean;
  loading: boolean;
  detail: MarketplaceAppDetail | null;
  ratings: AppRating[];
  installingId: string | null;
  rateScore: number;
  rateComment: string;
  rateSaving: boolean;
  marketplaceMeta: MarketplaceMeta | null;
  onClose: () => void;
  onInstall: (app: MarketplaceApp) => void;
  onRateScoreChange: (score: number) => void;
  onRateCommentChange: (comment: string) => void;
  onSaveRating: () => void;
  onDeleteRating: () => void;
};

export function MarketplaceAppDetailDrawer({
  open,
  loading,
  detail,
  ratings,
  installingId,
  rateScore,
  rateComment,
  rateSaving,
  marketplaceMeta,
  onClose,
  onInstall,
  onRateScoreChange,
  onRateCommentChange,
  onSaveRating,
  onDeleteRating,
}: Props) {
  const manifestItems = detail ? manifestResourceItems(detail.manifest ?? {}) : [];
  const canInstall = detail && !detail.installed && detail.status === "published";

  const title = loading ? "加载中…" : detail ? `${detail.icon || "📦"} ${detail.name}` : "应用详情";

  const description =
    detail && !loading
      ? [detail.category_name, detail.is_official ? "官方" : null, detail.installed ? "已安装" : marketplaceStatusLabel(detail.status, marketplaceMeta)]
          .filter(Boolean)
          .join(" · ")
      : undefined;

  return (
    <ResourceDialog
      open={open}
      size="drawer"
      title={title}
      description={description}
      onClose={onClose}
      footer={
        detail && !loading ? (
          <>
            <button type="button" className="btn-ghost" onClick={onClose}>
              关闭
            </button>
            {canInstall && (
              <button type="button" className="btn-primary" disabled={installingId === detail.id} onClick={() => onInstall(detail)}>
                {installingId === detail.id ? "安装中…" : "一键安装"}
              </button>
            )}
          </>
        ) : null
      }
    >
      {loading && <p className="py-12 text-center text-sm text-ink-muted">加载应用详情…</p>}

      {detail && !loading && (
        <div className="space-y-4">
          <div className="flex flex-col gap-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <MarketplaceStarDisplay value={detail.rating_avg} count={detail.rating_count} />
              <span className="text-ink-muted">
                v{detail.version} · {detail.install_count} 次安装
              </span>
            </div>
            <TagChips tags={detail.tags} />
          </div>

          <DetailSection title="应用说明">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{detail.description?.trim() || "暂无描述"}</p>
          </DetailSection>

          {manifestItems.length > 0 && (
            <DetailSection title="包含能力" hint="安装后将复制以下资源到本租户">
              <ul className="space-y-2 text-sm">
                {manifestItems.map((item) => (
                  <li key={item.key} className="flex flex-wrap items-baseline gap-x-2 rounded-lg border border-line-soft bg-surface px-3 py-2">
                    <span className="shrink-0 text-xs font-medium text-brand">{item.label}</span>
                    <span className="min-w-0 font-medium text-ink">{item.name}</span>
                    {item.hint && <span className="w-full text-xs text-ink-faint">{item.hint}</span>}
                  </li>
                ))}
              </ul>
            </DetailSection>
          )}

          {detail.review_note && detail.status === "rejected" && (
            <DetailSection title="审核说明">
              <p className="text-sm text-amber-800">{detail.review_note}</p>
            </DetailSection>
          )}

          {detail.installed ? (
            <DetailSection title="我的评分">
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => onRateScoreChange(s)}
                    className={`text-xl transition ${s <= rateScore ? "text-amber-500" : "text-ink-faint"}`}
                  >
                    ★
                  </button>
                ))}
              </div>
              <textarea
                className="input-field mt-2 min-h-[72px] w-full resize-y text-sm"
                placeholder="可选评价内容"
                value={rateComment}
                onChange={(e) => onRateCommentChange(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" disabled={rateSaving} onClick={onSaveRating} className="btn-primary text-xs">
                  {rateSaving ? "保存中…" : "保存评分"}
                </button>
                {detail.my_rating && (
                  <button type="button" disabled={rateSaving} onClick={onDeleteRating} className="btn-secondary text-xs">
                    删除评分
                  </button>
                )}
              </div>
            </DetailSection>
          ) : detail.status === "published" ? (
            <p className="text-sm text-ink-faint">安装后可对该应用评分</p>
          ) : null}

          {ratings.length > 0 && (
            <DetailSection title="用户评价">
              <ul className="max-h-56 space-y-2 overflow-y-auto text-sm">
                {ratings.map((r) => (
                  <li key={r.id} className="rounded-lg border border-line px-3 py-2">
                    <MarketplaceStarDisplay value={r.score} />
                    {r.comment && <p className="mt-1 text-ink-muted">{r.comment}</p>}
                    <p className="mt-1 text-xs text-ink-faint">{r.created_at.slice(0, 10)}</p>
                  </li>
                ))}
              </ul>
            </DetailSection>
          )}
        </div>
      )}
    </ResourceDialog>
  );
}
