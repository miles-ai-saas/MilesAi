"use client";

/** 分区切换链接（三分区：AI 工作台 · 业务中心 · 组织设置）。 */
import Link from "next/link";
import { getOtherSections, type AppSection } from "@/lib/nav-config";

export function SectionLinks({ current, className = "" }: { current: AppSection; className?: string }) {
  const others = getOtherSections(current);
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {others.map((target) => (
        <Link
          key={target.id}
          href={target.home}
          className="rounded-lg border border-line px-3 py-1.5 text-sm text-ink-muted transition hover:border-brand/30 hover:bg-brand-light hover:text-brand"
        >
          {target.label}
        </Link>
      ))}
    </div>
  );
}

/** 旧版兼容：双分区切换（AI 工作台 ↔ 组织设置）。 */
export function SectionLink({ section, className = "" }: { section: AppSection; className?: string }) {
  const others = getOtherSections(section);
  const target = others[0];
  if (!target) return null;
  return (
    <Link
      href={target.home}
      className={`rounded-lg border border-line px-3 py-1.5 text-sm text-ink-muted transition hover:border-brand/30 hover:bg-brand-light hover:text-brand ${className}`}
    >
      {target.label}
    </Link>
  );
}
