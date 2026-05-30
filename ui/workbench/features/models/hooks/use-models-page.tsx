"use client";

import { useCallback, useState } from "react";
import { useModelsForm } from "@/features/models/hooks/use-models-form";
import { useModelsList } from "@/features/models/hooks/use-models-list";
import { useModelsNavigation } from "@/features/models/hooks/use-models-navigation";

export function useModelsPage() {
  const listSlice = useModelsList();
  const navigation = useModelsNavigation();
  const [detailReloadKey, setDetailReloadKey] = useState(0);

  const reloadAll = useCallback(async () => {
    await listSlice.reload();
    setDetailReloadKey((k) => k + 1);
  }, [listSlice.reload]);

  const form = useModelsForm({
    reload: reloadAll,
    onDeleted: navigation.closeDetail,
  });

  return {
    ...listSlice,
    ...form,
    ...navigation,
    detailReloadKey,
  };
}

export type ModelsPageVm = ReturnType<typeof useModelsPage>;
