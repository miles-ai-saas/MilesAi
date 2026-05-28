"use client";

/** 旧详情页路由：重定向到列表并打开详情弹窗（`?task=id`）。 */

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function TaskDetailRedirectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    if (!id) {
      router.replace("/workbench/tasks");
      return;
    }
    router.replace(`/workbench/tasks?task=${encodeURIComponent(id)}`);
  }, [id, router]);

  return <p className="py-12 text-center text-sm text-ink-muted">正在打开任务详情…</p>;
}
