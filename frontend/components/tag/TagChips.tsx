import type { TagRef } from "@/lib/types";

export function TagChips({ tags }: { tags?: TagRef[] }) {
  if (!tags?.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {tags.map((t) => (
        <span
          key={t.id}
          className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] text-ink-muted"
        >
          {t.name}
        </span>
      ))}
    </div>
  );
}
