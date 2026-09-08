"use client";

import { useCallback, useEffect, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type AdminMarketplaceAppDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useMarketplaceReviewPage() {
  const ready = useRequireAdmin();
  const [reviewMode, setReviewMode] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminMarketplaceAppDetail | null>(null);
  const [rejectTarget, setRejectTarget] = useState<{ id: string; name: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listPendingMarketplaceApps(p, s), []),
    { enabled: ready && reviewMode === "platform" },
  );

  useEffect(() => {
    if (!ready) return;
    adminApi
      .getMarketplaceReviewMode()
      .then((res) => setReviewMode(res.review_mode))
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, [ready]);

  const forbidden = ready && reviewMode !== null && reviewMode !== "platform";

  const onApprove = async (id: string) => {
    setBusyId(id);
    setErr("");
    try {
      await adminApi.approveMarketplaceApp(id);
      setMsg("已通过并上架");
      setDetail(null);
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const onConfirmReject = async () => {
    if (!rejectTarget) return;
    setRejectLoading(true);
    setErr("");
    try {
      await adminApi.rejectMarketplaceApp(rejectTarget.id, rejectNote || undefined);
      setMsg("已驳回");
      setRejectTarget(null);
      setRejectNote("");
      setDetail(null);
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "驳回失败");
    } finally {
      setRejectLoading(false);
    }
  };

  const onView = async (id: string) => {
    setErr("");
    try {
      setDetail(await adminApi.getMarketplaceAppForReview(id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载详情失败");
    }
  };

  return {
    reviewMode,
    forbidden,
    detail,
    setDetail,
    rejectTarget,
    setRejectTarget,
    busyId,
    rejectLoading,
    rejectNote,
    setRejectNote,
    msg,
    err,
    list,
    onApprove,
    onConfirmReject,
    onView,
  };
}

export type MarketplaceReviewPageVm = ReturnType<typeof useMarketplaceReviewPage>;
