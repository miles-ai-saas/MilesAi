"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { AppInstall, AppRollbackPreview, AppUpgradePreview } from "@/lib/types";

function rollbackPreviewToUpgrade(p: AppRollbackPreview): AppUpgradePreview {
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

type Params = {
  setMsg: (msg: string) => void;
  reloadInstalls: () => Promise<void>;
};

export function useMarketplaceVersionOps({ setMsg, reloadInstalls }: Params) {
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [upgradeTarget, setUpgradeTarget] = useState<AppInstall | null>(null);
  const [upgradePreview, setUpgradePreview] = useState<AppUpgradePreview | null>(null);
  const [upgradePreviewLoading, setUpgradePreviewLoading] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<AppInstall | null>(null);
  const [rollbackPreview, setRollbackPreview] = useState<AppUpgradePreview | null>(null);
  const [rollbackPreviewLoading, setRollbackPreviewLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);

  const onOpenUpgrade = async (ins: AppInstall) => {
    setUpgradeTarget(ins);
    setUpgradePreview(null);
    setUpgradePreviewLoading(true);
    setMsg("");
    try {
      setUpgradePreview(await api.getMarketplaceUpgradePreview(ins.app_id));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载升级预览失败");
      setUpgradeTarget(null);
    } finally {
      setUpgradePreviewLoading(false);
    }
  };

  const closeUpgradeDialog = () => {
    if (upgrading) return;
    setUpgradeTarget(null);
    setUpgradePreview(null);
    setUpgradePreviewLoading(false);
  };

  const onConfirmUpgrade = async () => {
    if (!upgradeTarget) return;
    setUpgrading(upgradeTarget.app_id);
    setMsg("");
    try {
      const res = await api.upgradeMarketplaceApp(upgradeTarget.app_id);
      setMsg(res.message);
      setUpgradeTarget(null);
      setUpgradePreview(null);
      await reloadInstalls();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "升级失败");
    } finally {
      setUpgrading(null);
      setUpgradePreviewLoading(false);
    }
  };

  const onOpenRollback = async (ins: AppInstall) => {
    setRollbackTarget(ins);
    setRollbackPreview(null);
    setRollbackPreviewLoading(true);
    setMsg("");
    try {
      setRollbackPreview(rollbackPreviewToUpgrade(await api.getMarketplaceRollbackPreview(ins.app_id)));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载回滚预览失败");
      setRollbackTarget(null);
    } finally {
      setRollbackPreviewLoading(false);
    }
  };

  const closeRollbackDialog = () => {
    if (rollingBack) return;
    setRollbackTarget(null);
    setRollbackPreview(null);
    setRollbackPreviewLoading(false);
  };

  const onConfirmRollback = async () => {
    if (!rollbackTarget) return;
    setRollingBack(rollbackTarget.app_id);
    setMsg("");
    try {
      const res = await api.rollbackMarketplaceApp(rollbackTarget.app_id);
      setMsg(res.message);
      setRollbackTarget(null);
      setRollbackPreview(null);
      await reloadInstalls();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "回滚失败");
    } finally {
      setRollingBack(null);
      setRollbackPreviewLoading(false);
    }
  };

  return {
    upgrading,
    upgradeTarget,
    upgradePreview,
    upgradePreviewLoading,
    rollbackTarget,
    rollbackPreview,
    rollbackPreviewLoading,
    rollingBack,
    onOpenUpgrade,
    closeUpgradeDialog,
    onConfirmUpgrade,
    onOpenRollback,
    closeRollbackDialog,
    onConfirmRollback,
  };
}

export type MarketplaceVersionOps = ReturnType<typeof useMarketplaceVersionOps>;
