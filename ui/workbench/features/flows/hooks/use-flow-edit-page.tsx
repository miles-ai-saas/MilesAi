"use client";

import { useFlowEditCore } from "@/features/flows/hooks/use-flow-edit-core";
import { useFlowEditDebug } from "@/features/flows/hooks/use-flow-edit-debug";

export function useFlowEditPage() {
  const core = useFlowEditCore();
  const debug = useFlowEditDebug({
    id: core.id,
    graphRef: core.graphRef,
    graphTick: core.graphTick,
    busy: core.busy,
    setBusy: core.setBusy,
  });

  return {
    ...core,
    ...debug,
  };
}

export type FlowEditPageVm = ReturnType<typeof useFlowEditPage>;
