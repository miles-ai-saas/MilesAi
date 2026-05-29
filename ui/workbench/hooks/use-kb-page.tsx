"use client";

import { useRequireAuth } from "@/lib/auth-store";
import { useKbForm } from "@/hooks/use-kb-form";
import { useKbList, useKbModels } from "@/hooks/use-kb-list";

export function useKbPage() {
  const { ready } = useRequireAuth();
  const listSlice = useKbList();
  const models = useKbModels(ready);
  const form = useKbForm(listSlice, models);

  return {
    ...listSlice,
    textEmbeddingModels: models.textEmbeddingModels,
    clipModels: models.clipModels,
    ...form,
  };
}

export type KbPageVm = ReturnType<typeof useKbPage>;
