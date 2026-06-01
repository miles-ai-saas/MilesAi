"use client";

import type { ReactNode } from "react";
import { BusinessFlowStrip } from "@/features/business-dashboard/components/BusinessFlowStrip";
import { getFlowStep, type BusinessFlowStepId } from "@/features/business-dashboard/lib/business-flow";

type Props = {
  flowStep: BusinessFlowStepId;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  /** 资源类页面仍展示主链路，但不强制高亮当前步（如供应商） */
  flowHighlight?: boolean;
};

export function BizPageHero({ flowStep, title, subtitle, actions, flowHighlight = true }: Props) {
  const step = getFlowStep(flowStep);
  const heading = title ?? step?.label ?? "业务中心";
  const desc = subtitle ?? step?.description;

  return (
    <div className="mb-6 space-y-4">
      <BusinessFlowStrip current={flowHighlight ? flowStep : undefined} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">{heading}</h1>
          {desc ? <p className="mt-1 text-sm text-ink-muted">{desc}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
