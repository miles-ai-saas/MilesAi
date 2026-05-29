"use client";

/** 工具参数 schema 编辑（链路 §3）。 */
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
      {value.length > 0 && (
        <div className="hidden grid-cols-[1fr_120px_72px_56px] gap-2 px-3 text-[10px] font-medium uppercase tracking-wide text-ink-faint md:grid">
          <span>参数名</span>
          <span>类型</span>
          <span>必填</span>
          <span />
        </div>
      )}
      {value.map((row, idx) => (
        <div key={idx} className="grid gap-2 rounded-lg border border-line-soft bg-surface p-3 md:grid-cols-[1fr_120px_72px_56px] md:items-center">
          <input className="input-field w-full" placeholder="参数名" value={row.name} onChange={(e) => update(idx, { name: e.target.value })} />
          <select className="input-field w-full" value={row.type} onChange={(e) => update(idx, { type: e.target.value as ToolParameterSpec["type"] })}>
            <option value="string">string</option>
            <option value="integer">integer</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
          </select>
          <label className="flex items-center gap-2 text-xs text-ink-muted md:justify-center">
            <input type="checkbox" checked={Boolean(row.required)} onChange={(e) => update(idx, { required: e.target.checked })} />
            <span className="md:sr-only">必填</span>
            <span className="md:hidden">必填</span>
          </label>
          <button type="button" className="text-xs text-red-600 hover:underline md:text-center" onClick={() => remove(idx)}>
            删除
          </button>
          <input
            className="input-field w-full md:col-span-4"
            placeholder="描述（供 LLM 理解参数含义）"
            value={row.description ?? ""}
            onChange={(e) => update(idx, { description: e.target.value })}
          />
        </div>
      ))}
      <button
        type="button"
        className="w-full rounded-lg border border-dashed border-line py-2.5 text-sm text-ink-muted transition hover:border-brand hover:text-brand"
        onClick={() => onChange([...value, emptyRow()])}
      >
        + 添加参数
      </button>
    </div>
  );
}
