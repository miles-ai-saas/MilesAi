"use client";

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { GenerativeJobsMeta } from "@/lib/generative-job-labels";

export function useGenerativeJobMeta(enabled: boolean) {
  return useEnumMeta<GenerativeJobsMeta>(api.getGenerativeJobsMeta, enabled);
}
