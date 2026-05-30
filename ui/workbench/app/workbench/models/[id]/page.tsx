"use client";

/** 旧详情页路由：重定向到列表并打开详情弹窗（`?model=id`）。 */

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ModelDetailRedirectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    if (!id) {
      router.replace("/workbench/models");
      return;
    }
    router.replace(`/workbench/models?model=${encodeURIComponent(id)}`);
  }, [id, router]);

  return <p className="py-12 text-center text-sm text-ink-muted">正在打开模型详情…</p>;
}
