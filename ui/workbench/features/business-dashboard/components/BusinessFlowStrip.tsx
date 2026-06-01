"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BUSINESS_MAIN_FLOW, type BusinessFlowStepId } from "@/features/business-dashboard/lib/business-flow";
import { hasPermission } from "@/lib/permissions";
import { useAuthStore } from "@/lib/auth-store";
import { isNavActive } from "@/lib/nav-config";

type Props = {
  current?: BusinessFlowStepId;
  compact?: boolean;
};

export function BusinessFlowStrip({ current, compact }: Props) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const steps = BUSINESS_MAIN_FLOW.filter((s) => !s.permission || hasPermission(user, s.permission));

  if (steps.length === 0) return null;

  return (
    <nav aria-label="业务主链路" className="overflow-x-auto">
      <ol className="flex min-w-max items-center gap-1 text-xs">
        {steps.map((step, index) => {
          const routeActive = isNavActive(pathname, step.href);
          const isCurrent = current === step.id;
          return (
            <li key={step.id} className="flex items-center gap-1">
              {index > 0 ? <span className="px-0.5 text-ink-faint" aria-hidden>→</span> : null}
              <Link
                href={step.href}
                title={step.description}
                className={`rounded-full transition ${
                  compact ? "px-2.5 py-1" : "px-3 py-1.5"
                } ${
                  isCurrent
                    ? "bg-brand font-medium text-white"
                    : routeActive
                      ? "bg-brand-light font-medium text-brand"
                      : "bg-surface-muted text-ink-muted hover:bg-surface hover:text-ink"
                }`}
              >
                {compact ? step.shortLabel : step.label}
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
