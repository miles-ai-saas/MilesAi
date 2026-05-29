"use client";

import type { SkillImportResult, SysCategory } from "@/lib/types";

export type SkillImportDialogProps = {
  open: boolean;
  categories: SysCategory[];
  onClose: () => void;
  onDone: (result: SkillImportResult) => void;
};

export function SkillImportCategorySelect({
  categories,
  value,
  onChange,
}: {
  categories: SysCategory[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-ink-muted">
        技能分类 <span className="text-red-500">*</span>
      </span>
      <select className="input-field w-full" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">请选择</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SkillImportOverwriteToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-3 text-sm">
      <input type="checkbox" className="mt-1" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="font-medium text-ink">覆盖已有同名技能</span>
        <span className="mt-1 block text-xs text-ink-muted">开启后，若存在同名技能包，将以新导入内容覆盖原有数据；关闭则跳过同名项。</span>
      </span>
    </label>
  );
}
