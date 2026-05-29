import type { AppRollbackPreview, AppUpgradePreview, MarketplaceApp } from "@/lib/types";

export type MarketplaceMainView = "plaza" | "installs" | "mine" | "publish" | "review";

export function marketplaceAppSearchText(a: MarketplaceApp) {
  return `${a.name} ${a.description ?? ""} ${(a.tags ?? []).map((t) => t.name).join(" ")}`;
}

export function rollbackPreviewToUpgrade(p: AppRollbackPreview): AppUpgradePreview {
  return {
    app_id: p.app_id,
    app_name: p.app_name,
    installed_version: p.current_version,
    target_version: p.target_version,
    can_upgrade: p.can_rollback,
    has_changes: p.resources.some((r) => r.has_changes),
    message: p.message,
    resources: p.resources,
  };
}
