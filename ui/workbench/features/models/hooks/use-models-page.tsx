"use client";

import { useModelsForm } from "@/features/models/hooks/use-models-form";
import { useModelsList } from "@/features/models/hooks/use-models-list";

export function useModelsPage() {
  const listSlice = useModelsList();
  const form = useModelsForm({ reload: listSlice.reload });

  return {
    ...listSlice,
    ...form,
  };
}

export type ModelsPageVm = ReturnType<typeof useModelsPage>;
