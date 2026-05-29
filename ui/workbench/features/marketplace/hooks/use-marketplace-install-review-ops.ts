"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { AppInstallResult, MarketplaceApp } from "@/lib/types";
import type { MarketplaceMainView } from "@/features/marketplace/lib/marketplace-page-shared";

type Params = {
  setMsg: (msg: string) => void;
  mainView: MarketplaceMainView;
  reviewMode: string;
  showReviewTab: boolean;
  detailAppId: string | null;
  reloadApps: () => Promise<void>;
  reloadInstalls: () => Promise<void>;
  reloadMyApps: () => Promise<void>;
  reloadPendingApps: () => Promise<void>;
  reloadDetail: (appId: string) => Promise<void>;
};

export function useMarketplaceInstallReviewOps({
  setMsg,
  mainView,
  reviewMode,
  showReviewTab,
  detailAppId,
  reloadApps,
  reloadInstalls,
  reloadMyApps,
  reloadPendingApps,
  reloadDetail,
}: Params) {
  const [installing, setInstalling] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<MarketplaceApp | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [lastResult, setLastResult] = useState<AppInstallResult | null>(null);

  const onInstall = async (app: MarketplaceApp) => {
    if (app.installed) {
      setMsg("该应用已安装");
      return;
    }
    setInstalling(app.id);
    setMsg("");
    try {
      const res = await api.installMarketplaceApp(app.id);
      setLastResult(res);
      setMsg(res.message);
      await reloadApps();
      if (mainView === "installs") await reloadInstalls();
      if (detailAppId === app.id) await reloadDetail(app.id);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "安装失败");
    } finally {
      setInstalling(null);
    }
  };

  const onTrial = async (app: MarketplaceApp) => {
    if (app.installed) {
      setMsg("该应用已安装");
      return;
    }
    setInstalling(app.id);
    setMsg("");
    try {
      const res = await api.trialMarketplaceApp(app.id);
      setLastResult(res);
      setMsg("试用已安装，24 小时内有效");
      await reloadApps();
      if (detailAppId === app.id) await reloadDetail(app.id);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "试用失败");
    } finally {
      setInstalling(null);
    }
  };

  const onSubmitReview = async (appId: string) => {
    setPublishing(appId);
    setMsg("");
    try {
      await api.publishMarketplaceApp(appId);
      setMsg(reviewMode === "off" ? "已上架" : reviewMode === "platform" ? "已提交，等待平台运营审核" : "已提交审核，通过后将在应用广场展示");
      await reloadMyApps();
      if (showReviewTab) await reloadPendingApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "提交失败");
    } finally {
      setPublishing(null);
    }
  };

  const onApprove = async (appId: string) => {
    setReviewing(appId);
    setMsg("");
    try {
      await api.approveMarketplaceApp(appId);
      setMsg("已通过审核并上架");
      await reloadPendingApps();
      await reloadApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setReviewing(null);
    }
  };

  const onReject = (app: MarketplaceApp) => setRejectTarget(app);

  const onConfirmReject = async (note: string) => {
    if (!rejectTarget) return;
    setRejectLoading(true);
    setMsg("");
    try {
      await api.rejectMarketplaceApp(rejectTarget.id, note || undefined);
      setMsg("已驳回该应用");
      setRejectTarget(null);
      await reloadPendingApps();
      await reloadMyApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "驳回失败");
    } finally {
      setRejectLoading(false);
    }
  };

  return {
    installing,
    publishing,
    reviewing,
    rejectTarget,
    setRejectTarget,
    rejectLoading,
    lastResult,
    setLastResult,
    onInstall,
    onTrial,
    onSubmitReview,
    onApprove,
    onReject,
    onConfirmReject,
  };
}

export type MarketplaceInstallReviewOps = ReturnType<typeof useMarketplaceInstallReviewOps>;
