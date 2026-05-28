"use client";

/** 工作台/系统分区切换链接（链路 §7）。 */
import Link from "next/link";
import { getOtherSection, type AppSection } from "@/lib/nav-config";

export function SectionLink({ section, className = "" }: { section: AppSection; className?: string }) {
  const target = getOtherSection(section);
  return (
    <Link
      href={target.home}
      className={`rounded-lg border border-line px-3 py-1.5 text-sm text-ink-muted transition hover:border-brand/30 hover:bg-brand-light hover:text-brand ${className}`}
    >
      {target.label}
    </Link>
  );
}
