"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type AdminTemplatePack } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export type TemplatePackReviewTab = "pending" | "published";

export function useTemplatePackReviewPage() {
  const ready = useRequireAdmin();
  const [tab, setTab] = useState<TemplatePackReviewTab>("pending");
  const [detail, setDetail] = useState<AdminTemplatePack | null>(null);
  const [rejectTarget, setRejectTarget] = useState<{ id: string; name: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const pendingList = usePagedList(
    useCallback((p, s) => adminApi.listPendingTemplatePacks(p, s), []),
    { enabled: ready && tab === "pending" },
  );

  const publishedList = usePagedList(
    useCallback((p, s) => adminApi.listPublishedTemplatePacks(p, s), []),
    { enabled: ready && tab === "published" },
  );

  const list = tab === "pending" ? pendingList : publishedList;

  const onApprove = async (id: string) => {
    setBusyId(id);
    setErr("");
    try {
      await adminApi.approveTemplatePack(id);
      setMsg("已通过并上架");
      setDetail(null);
      await pendingList.reload();
      await publishedList.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const onUnpublish = async (id: string) => {
    if (!window.confirm("确认下架？模板将从广场隐藏。")) return;
    setBusyId(id);
    setErr("");
    try {
      const updated = await adminApi.unpublishTemplatePack(id);
      setMsg("已下架");
      setDetail(updated);
      await publishedList.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const onToggleFeatured = async (id: string, featured: boolean) => {
    setBusyId(id);
    setErr("");
    try {
      const updated = await adminApi.setTemplatePackFeatured(id, featured);
      setMsg(featured ? "已设为精选" : "已取消精选");
      setDetail(updated);
      await publishedList.reload();
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
      await pendingList.reload();
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
    setMsg,
    err,
    setErr,
  };
}

export type TemplatePackReviewPageVm = ReturnType<typeof useTemplatePackReviewPage>;
