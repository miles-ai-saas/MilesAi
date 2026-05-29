"use client";

/** 提示词模板列表（链路 §3 + §4 `usePromptMeta`）。 */

import { PromptsPageView, usePromptsPage } from "@/features/prompts";

export default function PromptsPage() {
  const vm = usePromptsPage();
  return <PromptsPageView vm={vm} />;
}
