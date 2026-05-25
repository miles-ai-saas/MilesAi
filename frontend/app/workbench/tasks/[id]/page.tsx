"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { taskStatusLabel } from "@/lib/task-labels";
import type { TaskRecord } from "@/lib/types";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setTask(await api.getTask(id));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!ready || !id) return;
    reload();
  }, [ready, id, reload]);

  useEffect(() => {
    if (!task || !["pending", "running"].includes(task.status)) return;
    const t = setInterval(reload, 5000);
    return () => clearInterval(t);
  }, [task, reload]);

  const act = async (action: "cancel" | "retry") => {
    setMsg("");
    try {
      if (action === "cancel") await api.cancelTask(id);
      else await api.retryTask(id);
      setMsg(action === "cancel" ? "已取消" : "已重新提交");
      await reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  if (loading) return <p className="text-ink-muted">加载中…</p>;
  if (!task) return <p className="text-red-600">{msg || "任务不存在"}</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <Link href="/workbench/tasks" className="text-brand hover:underline">
          任务
        </Link>
        <span>/</span>
        <span className="text-ink">{task.task_name}</span>
      </div>

      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-ink">{task.task_name}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              状态：{taskStatusLabel(task.status)}
            </p>
          </div>
          <div className="flex gap-2">
            {["pending", "running"].includes(task.status) && (
              <button type="button" className="btn-ghost text-red-600" onClick={() => act("cancel")}>
                取消
              </button>
            )}
            {["failed", "cancelled", "success"].includes(task.status) &&
              task.resource_type === "document" && (
                <button type="button" className="btn-primary" onClick={() => act("retry")}>
                  重试
                </button>
              )}
          </div>
        </div>

        <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-ink-faint">任务 ID</dt>
            <dd className="font-mono text-xs text-ink">{task.id}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">Celery ID</dt>
            <dd className="font-mono text-xs text-ink break-all">{task.celery_task_id}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">资源类型</dt>
            <dd>{task.resource_type || "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">资源 ID</dt>
            <dd className="font-mono text-xs">{task.resource_id || "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">创建时间</dt>
            <dd>{task.created_at.slice(0, 19).replace("T", " ")}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">更新时间</dt>
            <dd>{task.updated_at.slice(0, 19).replace("T", " ")}</dd>
          </div>
        </dl>

        {task.fail_reason && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">失败原因</p>
            <pre className="mt-2 whitespace-pre-wrap text-xs">{task.fail_reason}</pre>
          </div>
        )}

        {task.resource_type === "document" && task.resource_id && (
          <p className="mt-4">
            <Link
              href={`/workbench/kb`}
              className="text-sm text-brand hover:underline"
              onClick={(e) => {
                e.preventDefault();
                router.push("/workbench/kb");
              }}
            >
              前往知识库查看文档
            </Link>
          </p>
        )}

        {msg && <p className="mt-4 text-sm text-ink-muted">{msg}</p>}
      </section>
    </div>
  );
}
