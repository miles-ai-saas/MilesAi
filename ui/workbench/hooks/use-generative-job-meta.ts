"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";

export function useGenerativeJobMeta(enabled: boolean) {
  const [meta, setMeta] = useState<GenerativeJobsMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getGenerativeJobsMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
