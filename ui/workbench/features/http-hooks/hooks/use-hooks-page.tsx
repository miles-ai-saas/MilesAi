"use client";

import { useHooksBindings } from "@/hooks/use-hooks-bindings";
import { useHooksForm, useHooksList } from "@/hooks/use-hooks-list";

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
