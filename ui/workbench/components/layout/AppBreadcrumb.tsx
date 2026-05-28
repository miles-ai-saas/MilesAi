/** 系统管理面包屑（链路 §7）。 */

import Link from "next/link";
import type { BreadcrumbItem } from "@/lib/nav-config";

export function AppBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="面包屑" className="flex min-w-0 items-center gap-1.5 text-sm">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={`${item.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <span className="text-ink-faint">/</span>}
            {item.href && !isLast ? (
              <Link href={item.href} className="truncate text-ink-muted transition hover:text-brand">
                {item.label}
              </Link>
            ) : (
              <span className={`truncate ${isLast ? "font-medium text-ink" : "text-ink-muted"}`}>{item.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
