"use client";

import { useHooksBindings } from "@/features/http-hooks/hooks/use-hooks-bindings";
import { useHooksForm, useHooksList } from "@/features/http-hooks/hooks/use-hooks-list";

export function useHooksPage() {
  const listSlice = useHooksList();
  const form = useHooksForm(listSlice);
  const bindings = useHooksBindings(listSlice);

  return {
    ...listSlice,
    ...form,
    ...bindings,
  };
}

export type HooksPageVm = ReturnType<typeof useHooksPage>;
