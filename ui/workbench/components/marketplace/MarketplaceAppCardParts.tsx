"use client";

import { MarketplaceStarDisplay } from "@/components/marketplace/MarketplaceStarDisplay";
import { TagChips } from "@/components/tag/TagChips";
import { CardActions } from "@/components/resource/CardActions";
import { marketplaceVisibilityLabel } from "@/lib/marketplace-labels";
import type { MarketplaceApp, MarketplaceMeta } from "@/lib/types";

export function MarketplaceAppCardMeta({ app, marketplaceMeta }: { app: MarketplaceApp; marketplaceMeta: MarketplaceMeta | null }) {
  return (
    <span className="flex flex-col gap-2 text-xs">
      <span className="flex flex-wrap items-center gap-2">
        <MarketplaceStarDisplay value={app.rating_avg} count={app.rating_count} />
        <span className="text-ink-muted">
          v{app.version}
          {app.category_name && ` · ${app.category_name}`} · {app.install_count} 次安装
          {app.visibility && app.visibility !== "public" ? ` · ${marketplaceVisibilityLabel(app.visibility, marketplaceMeta)}` : ""}
        </span>
      </span>
      <TagChips tags={app.tags} />
    </span>
  );
}

type AppActionMode = "plaza" | "mine" | "review";

export function MarketplaceAppCardActions({
  app,
  mode,
  installing,
  publishing,
  reviewing,
  onDetail,
  onInstall,
  onTrial,
  onSubmitReview,
  onApprove,
  onReject,
}: {
  app: MarketplaceApp;
  mode: AppActionMode;
  installing: string | null;
  publishing: string | null;
  reviewing: string | null;
  onDetail: (appId: string) => void;
  onInstall: (app: MarketplaceApp) => void;
  onTrial: (app: MarketplaceApp) => void;
  onSubmitReview: (appId: string) => void;
  onApprove: (appId: string) => void;
  onReject: (app: MarketplaceApp) => void;
}) {
  if (mode === "plaza") {
    return (
      <CardActions
        actions={[
          { label: "详情", variant: "primary", onClick: () => onDetail(app.id) },
          {
            label: app.installed ? "已安装" : installing === app.id ? "安装中…" : "安装",
            onClick: () => onInstall(app),
            disabled: app.installed || installing === app.id,
          },
          ...(app.installed || installing === app.id ? [] : [{ label: "试用", onClick: () => onTrial(app) }]),
        ]}
      />
    );
  }
  if (mode === "mine") {
    const actions: Parameters<typeof CardActions>[0]["actions"] = [{ label: "详情", variant: "primary", onClick: () => onDetail(app.id) }];
    if (app.status === "draft" || app.status === "rejected") {
      actions.push({
        label: publishing === app.id ? "提交中…" : app.status === "rejected" ? "重新提交审核" : "提交审核",
        onClick: () => onSubmitReview(app.id),
        disabled: publishing === app.id,
      });
    }
    return <CardActions actions={actions} />;
  }
  return (
    <CardActions
      actions={[
        { label: "预览", variant: "primary", onClick: () => onDetail(app.id) },
        {
          label: reviewing === app.id ? "处理中…" : "通过",
          onClick: () => onApprove(app.id),
          disabled: reviewing === app.id,
        },
        {
          label: "驳回",
          variant: "danger",
          onClick: () => onReject(app),
          disabled: reviewing === app.id,
        },
      ]}
    />
  );
}
