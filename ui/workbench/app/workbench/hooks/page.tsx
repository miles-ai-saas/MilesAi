"use client";

/** 钩子列表（链路 §3 + §4）：CRUD、绑定规则、执行记录 + `useHookMeta`。 */

import { HookBindingsDialog, HookCatalogView, HookFormDialog, useHooksPage } from "@/features/http-hooks";

export default function HooksPage() {
  const vm = useHooksPage();
  return (
    <>
      <HookCatalogView vm={vm} />
      <HookFormDialog vm={vm} />
      <HookBindingsDialog vm={vm} />
      {vm.confirmDialog}
    </>
  );
}
