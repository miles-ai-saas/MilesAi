"use client";

/**
 * 拉取 GET /tasks/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
 */


import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TaskMeta } from "@/lib/types";

export function useTaskMeta(enabled = true) {
  const [meta, setMeta] = useState<TaskMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getTaskMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
