"use client";

/** Cron 表达式预览（链路 §10）。 */
import { buildCronExpr, describeCron, type CronParts } from "@/lib/cron-celery";

type Props = {
  parts: CronParts;
};

export function CronExpressionPreview({ parts }: Props) {
  const expr = buildCronExpr(parts);
  const description = describeCron(expr);

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-ink">Cron 表达式</p>
      <input
        readOnly
        value={expr}
        className="input-field w-full font-mono text-sm bg-surface-muted"
        aria-label="Cron 表达式"
      />
      <p className="text-xs text-ink-muted">{description}</p>
    </div>
  );
}
