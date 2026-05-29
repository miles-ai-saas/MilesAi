"use client";

import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { TagChips } from "@/components/tag/TagChips";
import { skillActiveLabel, skillSourceTypeLabel } from "@/lib/skill-labels";
import { formatSkillUpdated } from "@/lib/skills-page-shared";
import type { SkillMeta, SkillPackage } from "@/lib/types";

export function SkillCard({
  skill,
  skillMeta,
  onOpen,
  onDelete,
  onToggle,
}: {
  skill: SkillPackage;
  skillMeta: SkillMeta | null;
  onOpen: () => void;
  onDelete: () => Promise<void>;
  onToggle: () => Promise<void>;
}) {
  return (
    <ResourceItemCard
      title={skill.name}
      description={skill.description || "暂无描述"}
      badge={skill.is_active ? skillSourceTypeLabel(skill.source_type, skillMeta) : skillActiveLabel(false, skillMeta)}
      onClick={onOpen}
      meta={
        <>
          <span className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            {skill.category_name ? <span className="rounded bg-surface-muted px-1.5 py-0.5">{skill.category_name}</span> : null}
            <span>更新于 {formatSkillUpdated(skill.updated_at)}</span>
          </span>
          <TagChips tags={skill.tags} />
        </>
      }
      actions={
        <CardActions
          actions={[
            { label: "编辑", onClick: onOpen, variant: "primary" },
            { label: skill.is_active ? "停用" : "启用", onClick: onToggle },
            { label: "删除", onClick: onDelete, variant: "danger" },
          ]}
        />
      }
    />
  );
}
