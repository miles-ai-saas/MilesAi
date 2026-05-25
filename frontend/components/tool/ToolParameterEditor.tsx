"use client";

import type { ToolParameterSpec } from "@/lib/types";

type Props = {
  value: ToolParameterSpec[];
  onChange: (v: ToolParameterSpec[]) => void;
};

const emptyRow = (): ToolParameterSpec => ({
  name: "",
  type: "string",
  description: "",
  required: false,
});

export function ToolParameterEditor({ value, onChange }: Props) {
  const update = (idx: number, patch: Partial<ToolParameterSpec>) => {
    onChange(value.map((row, i) => (i === idx ? { ...row, ...patch } : row)));
  };

  const remove = (idx: number) => {
    onChange(value.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      {value.map((row, idx) => (
        <div
          key={idx}
          className="grid gap-2 rounded-lg border border-line-soft p-3 sm:grid-cols-2"
        >
          <input
            className="input-field w-full"
            placeholder="参数名"
            value={row.name}
            onChange={(e) => update(idx, { name: e.target.value })}
          />
          <select
            className="input-field w-full"
            value={row.type}
            onChange={(e) =>
              update(idx, { type: e.target.value as ToolParameterSpec["type"] })
            }
          >
            <option value="string">string</option>
            <option value="integer">integer</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
          </select>
          <input
            className="input-field w-full sm:col-span-2"
            placeholder="描述"
            value={row.description ?? ""}
            onChange={(e) => update(idx, { description: e.target.value })}
          />
          <label className="flex items-center gap-2 text-xs text-ink-muted">
            <input
              type="checkbox"
              checked={Boolean(row.required)}
              onChange={(e) => update(idx, { required: e.target.checked })}
            />
            必填
          </label>
          <button
            type="button"
            className="text-xs text-red-600 hover:underline"
            onClick={() => remove(idx)}
          >
            删除
          </button>
        </div>
      ))}
      <button
        type="button"
        className="w-full rounded-lg border border-dashed border-line py-2 text-sm text-ink-muted hover:border-brand hover:text-brand"
        onClick={() => onChange([...value, emptyRow()])}
      >
        + 添加参数
      </button>
    </div>
  );
}
