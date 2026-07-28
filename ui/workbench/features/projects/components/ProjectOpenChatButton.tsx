"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  buildAgentChatDeepLink,
  projectAiContextToStored,
} from "@/features/projects/lib/business-context";
import { api } from "@/lib/api";
import type { BizProjectAiContext } from "@/lib/types";

type Props = {
  projectId: string;
  className?: string;
};

/** 项目详情页头主入口：预取 AI 上下文后带项目信息打开对话。 */
export function ProjectOpenChatButton({ projectId, className }: Props) {
  const [ctx, setCtx] = useState<BizProjectAiContext | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setReady(false);
    api
      .getProjectAiContext(projectId)
      .then((data) => {
        if (!cancelled) setCtx(data);
      })
      .catch(() => {
        if (!cancelled) setCtx(null);
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const href = ctx
    ? buildAgentChatDeepLink({
        projectId,
        bizContext: projectAiContextToStored(ctx),
      })
    : `/workbench/agents/chat/?projectId=${encodeURIComponent(projectId)}&biz=1`;

  return (
    <Link
      href={href}
      className={className ?? "btn-primary shrink-0 text-sm"}
      aria-busy={!ready}
      title={ctx && !ctx.rag_enabled ? "涉密项目：对话不会引用外部知识库" : "带项目上下文打开智能体对话"}
    >
      打开对话
    </Link>
  );
}
