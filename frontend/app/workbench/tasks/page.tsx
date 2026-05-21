"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout, type ResourceTab } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { TaskRecord } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

const TABS: ResourceTab[] = [
  { key: "", label: "全部" },
  { key: "pending", label: "等待中" },
  { key: "running", label: "运行中" },
  { key: "failed", label: "失败" },
  { key: "success", label: "成功" },
];

export default function TasksPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [msg, setMsg] = useState("");

  const list = usePagedList(
    useCallback((p, s) => api.listTasks(p, s, filter || undefined), [filter]),
    { enabled: ready, resetKey: filter },
  );

  useEffect(() => {
    if (!ready) return;
    const t = setInterval(() => list.reload(), 8000);
    return () => clearInterval(t);
  }, [ready, list.reload, filter]);

  const filtered = useMemo(
    () =>
      filterBySearch(
        list.items,
        search,
        (t) => `${t.task_name} ${t.celery_task_id} ${t.resource_type ?? ""}`,
      ),
    [list.items, search],
  );

  const act = async (id: string, action: "cancel" | "retry") => {
    setMsg("");
    try {
      if (action === "cancel") await api.cancelTask(id);
      else await api.retryTask(id);
      setMsg(action === "cancel" ? "已取消" : "已重新提交");
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  return (
    <ResourceListLayout
      title="任务"
      description="查看文档入库等异步任务执行状态，支持取消与重试（每 8 秒自动刷新）。"
      searchPlaceholder="搜索任务名称"
      search={search}
      onSearchChange={setSearch}
      tabs={TABS}
      activeTab={filter}
      onTabChange={setFilter}
      loading={list.loading}
      headerAction={
        msg ? <span className="text-xs text-ink-muted">{msg}</span> : undefined
      }
      footer={
        !list.loading ? (
          <ResourceListFooter
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
          />
        ) : null
      }
    >
      {filtered.map((t: TaskRecord) => (
        <ResourceItemCard
          key={t.id}
          title={t.task_name}
          description={t.fail_reason ?? `任务 ID ${t.celery_task_id.slice(0, 16)}…`}
          badge={STATUS_LABEL[t.status] || t.status}
          meta={
            <span>
              {t.resource_type || "—"}
              {t.resource_id ? ` · ${String(t.resource_id).slice(0, 8)}…` : ""}
              <br />
              {t.created_at.slice(0, 19).replace("T", " ")}
            </span>
          }
          actions={
            <>
              <Link
                href={`/workbench/tasks/${t.id}`}
                className="text-xs text-brand hover:underline"
              >
                详情
              </Link>
              {["pending", "running"].includes(t.status) && (
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline"
                  onClick={() => act(t.id, "cancel")}
                >
                  取消
                </button>
              )}
              {["failed", "cancelled", "success"].includes(t.status) &&
                t.resource_type === "document" && (
                  <button
                    type="button"
                    className="text-xs text-brand hover:underline"
                    onClick={() => act(t.id, "retry")}
                  >
                    重试
                  </button>
                )}
            </>
          }
        />
      ))}
    </ResourceListLayout>
  );
}
