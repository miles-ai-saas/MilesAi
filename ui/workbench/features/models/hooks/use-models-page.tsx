"use client";

import { useModelsForm } from "@/hooks/use-models-form";
import { useModelsList } from "@/hooks/use-models-list";

export function useModelsPage() {
  const listSlice = useModelsList();
  const form = useModelsForm({ reload: listSlice.reload });

  return {
    ...listSlice,
    ...form,
  };
}

export type ModelsPageVm = ReturnType<typeof useModelsPage>;
