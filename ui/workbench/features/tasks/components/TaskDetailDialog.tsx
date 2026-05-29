"use client";

/** 异步任务详情弹窗（链路 §3）：`api.getTask`、手动刷新、取消/重试。 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { taskStatusBadgeClass, taskStatusLabel } from "@/features/tasks/lib/task-labels";
import type { TaskMeta, TaskRecord } from "@/lib/types";

type Props = {
  open: boolean;
  taskId: string | null;
  taskMeta?: TaskMeta | null;
  onClose: () => void;
  /** 取消/重试成功后通知列表刷新 */
  onChanged?: () => void;
};

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children}</dd>
    </div>
  );
}

export function canCancelTask(task: TaskRecord) {
  return ["pending", "running"].includes(task.status);
}

export function canRetryTask(task: TaskRecord) {
  return ["failed", "cancelled", "success"].includes(task.status) && task.resource_type === "document";
}

export function TaskDetailDialog({ open, taskId, taskMeta, onClose, onChanged }: Props) {
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);

  const reload = useCallback(async () => {
    if (!taskId) return;
    setLoading(true);
    try {
      const row = await api.getTask(taskId);
      setTask(row);
      setMsg("");
    } catch (e) {
      setTask(null);
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (!open || !taskId) {
      setTask(null);
      setMsg("");
      return;
    }
    void reload();
  }, [open, taskId, reload]);

  const act = async (action: "cancel" | "retry") => {
    if (!taskId) return;
    setActing(true);
    setMsg("");
    try {
      if (action === "cancel") await api.cancelTask(taskId);
      else await api.retryTask(taskId);
      setMsg(action === "cancel" ? "已取消" : "已重新提交");
      await reload();
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setActing(false);
    }
  };

  const title = task?.task_name ?? (loading ? "加载中…" : "任务详情");

  return (
    <ResourceDialog
      open={open}
      title={title}
      description={task ? `状态：${taskStatusLabel(task.status, taskMeta)}` : undefined}
      size="lg"
      onClose={onClose}
      footer={
        task ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" className="btn-ghost text-sm" disabled={loading || acting} onClick={() => void reload()}>
              {loading ? "刷新中…" : "刷新"}
            </button>
            {canCancelTask(task) && (
              <button type="button" className="btn-ghost text-red-600" disabled={acting} onClick={() => void act("cancel")}>
                取消任务
              </button>
            )}
            {canRetryTask(task) && (
              <button type="button" className="btn-primary" disabled={acting} onClick={() => void act("retry")}>
                重试
              </button>
            )}
            <button type="button" className="btn-secondary" onClick={onClose}>
              关闭
            </button>
          </div>
        ) : (
          <div className="flex justify-end">
            <button type="button" className="btn-secondary" onClick={onClose}>
              关闭
            </button>
          </div>
        )
      }
    >
      {loading && !task && <p className="text-sm text-ink-muted">加载中…</p>}
      {!loading && !task && <p className="text-sm text-red-600">{msg || "任务不存在"}</p>}
      {task && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${taskStatusBadgeClass(task.status)}`}>
              {taskStatusLabel(task.status, taskMeta)}
            </span>
          </div>

          <dl className="grid gap-4 sm:grid-cols-2">
            <DetailField label="任务 ID">
              <span className="font-mono text-xs">{task.id}</span>
            </DetailField>
            <DetailField label="Celery ID">
              <span className="break-all font-mono text-xs">{task.celery_task_id}</span>
            </DetailField>
            <DetailField label="资源类型">{task.resource_type || "—"}</DetailField>
            <DetailField label="资源 ID">
              <span className="font-mono text-xs">{task.resource_id || "—"}</span>
            </DetailField>
            <DetailField label="创建时间">{new Date(task.created_at).toLocaleString("zh-CN")}</DetailField>
            <DetailField label="更新时间">{new Date(task.updated_at).toLocaleString("zh-CN")}</DetailField>
          </dl>

          {task.fail_reason && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <p className="font-medium">失败原因</p>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{task.fail_reason}</pre>
            </div>
          )}

          {task.resource_type === "document" && task.resource_id && (
            <p>
              <Link href="/workbench/kb" className="text-sm text-brand hover:underline">
                前往知识库查看文档
              </Link>
            </p>
          )}

          {task.resource_type === "generative_job" && task.resource_id && (
            <p>
              <Link href={`/workbench/tasks?category=generative&job=${encodeURIComponent(task.resource_id)}`} className="text-sm text-brand hover:underline">
                在生成任务中查看详情 →
              </Link>
            </p>
          )}

          {msg && <p className="text-sm text-ink-muted">{msg}</p>}
        </div>
      )}
    </ResourceDialog>
  );
}
