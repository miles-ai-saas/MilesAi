"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BUSINESS_MAIN_FLOW, getFlowStep, type BusinessFlowStepId } from "@/features/business-dashboard/lib/business-flow";
import { hasPermission } from "@/lib/permissions";
import { useAuthStore } from "@/lib/auth-store";
import { isNavActive } from "@/lib/nav-config";

type Props = {
  current?: BusinessFlowStepId;
  compact?: boolean;
};

function FlowChip({
  href,
  label,
  title,
  active,
  compact,
}: {
  href: string;
  label: string;
  title?: string;
  active: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      href={href}
      title={title}
      className={`rounded-full transition ${
        compact ? "px-2.5 py-1" : "px-3 py-1.5"
      } ${
        active
          ? "bg-brand font-medium text-white"
          : "bg-surface-muted text-ink-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
}

export function BusinessFlowStrip({ current, compact }: Props) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const steps = BUSINESS_MAIN_FLOW.filter((s) => !s.permission || hasPermission(user, s.permission));
  const overview = getFlowStep("dashboard");
  const showOverview = overview && (!overview.permission || hasPermission(user, overview.permission));

  if (!showOverview && steps.length === 0) return null;

  return (
    <nav aria-label="业务主链路" className="overflow-x-auto">
      <ol className="flex min-w-max items-center gap-1 text-xs">
        {showOverview && overview ? (
          <li className="flex items-center gap-1">
            <FlowChip
              href={overview.href}
              label={compact ? overview.shortLabel : overview.label}
              title={overview.description}
              active={current === "dashboard" || isNavActive(pathname, overview.href)}
              compact={compact}
            />
            {steps.length > 0 ? <span className="px-0.5 text-ink-faint" aria-hidden>→</span> : null}
          </li>
        ) : null}
        {steps.map((step, index) => {
          const routeActive = isNavActive(pathname, step.href);
          const isCurrent = current === step.id;
          return (
            <li key={step.id} className="flex items-center gap-1">
              {index > 0 ? <span className="px-0.5 text-ink-faint" aria-hidden>→</span> : null}
              <FlowChip
                href={step.href}
                label={compact ? step.shortLabel : step.label}
                title={step.description}
                active={isCurrent || routeActive}
                compact={compact}
              />
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
