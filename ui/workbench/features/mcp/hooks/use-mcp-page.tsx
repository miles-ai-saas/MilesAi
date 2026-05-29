"use client";

import { useMcpForm } from "@/features/mcp/hooks/use-mcp-form";
import { useMcpList, useMcpViewing } from "@/features/mcp/hooks/use-mcp-list";

export function useMcpPage() {
  const listSlice = useMcpList();
  const viewing = useMcpViewing(listSlice.list.items);
  const form = useMcpForm(listSlice, viewing);

  return {
    ...listSlice,
    ...viewing,
    ...form,
  };
}

export type McpPageVm = ReturnType<typeof useMcpPage>;
