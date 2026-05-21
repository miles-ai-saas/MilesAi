"use client";

import Link from "next/link";
import { getOtherSection, type AppSection } from "@/lib/nav-config";

export function SectionLink({ section }: { section: AppSection }) {
  const target = getOtherSection(section);
  return (
    <Link
      href={target.home}
      className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-sm text-ink-muted transition hover:border-brand/30 hover:bg-brand-light hover:text-brand"
    >
      {target.label}
    </Link>
  );
}
