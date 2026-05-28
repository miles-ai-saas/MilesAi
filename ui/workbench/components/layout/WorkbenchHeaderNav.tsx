"use client";

/** 工作台顶栏导航（链路 §7）：消费 `nav-config.WORKBENCH_NAV`。 */

import Link from "next/link";
import { Fragment } from "react";
import { WORKBENCH_NAV, isNavActive } from "@/lib/nav-config";

export function WorkbenchHeaderNav({ pathname }: { pathname: string }) {
  return (
    <nav className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto px-2">
      {WORKBENCH_NAV.map((group, groupIndex) => (
        <Fragment key={group.title}>
          {groupIndex > 0 && <span className="mx-1.5 h-4 w-px shrink-0 bg-line" aria-hidden />}
          {group.items.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link key={item.href} href={item.href} className={`header-nav-item shrink-0 ${active ? "header-nav-item-active" : ""}`}>
                {item.label}
              </Link>
            );
          })}
        </Fragment>
      ))}
    </nav>
  );
}
