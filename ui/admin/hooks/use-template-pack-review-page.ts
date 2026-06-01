"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type AdminTemplatePack } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useTemplatePackReviewPage() {
  const ready = useRequireAdmin();
  const [detail, setDetail] = useState<AdminTemplatePack | null>(null);
  const [rejectTarget, setRejectTarget] = useState<{ id: string; name: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listPendingTemplatePacks(p, s), []),
    { enabled: ready },
  );

  const onApprove = async (id: string) => {
    setBusyId(id);
    setErr("");
    try {
      await adminApi.approveTemplatePack(id);
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
      await adminApi.rejectTemplatePack(rejectTarget.id, rejectNote.trim() || undefined);
      setMsg("已驳回");
      setRejectTarget(null);
      setRejectNote("");
      setDetail(null);
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setRejectLoading(false);
    }
  };

  const loadDetail = async (id: string) => {
    setErr("");
    try {
      setDetail(await adminApi.getTemplatePackForReview(id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    }
  };

  return {
    ready,
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
    onConfirmReject,
    msg,
    setMsg,
    err,
    setErr,
  };
}

export type TemplatePackReviewPageVm = ReturnType<typeof useTemplatePackReviewPage>;
