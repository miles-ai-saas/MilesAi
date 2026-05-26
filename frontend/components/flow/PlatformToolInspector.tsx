"use client";

/** PlatformTool 节点：catalog 选工具 + 参数 schema 表单（链路 §6 Phase 2）。 */
import { useMemo } from "react";
import type { ToolCatalogItem, ToolParameterSpec } from "@/lib/types";

function defaultParamsFromSpec(parameters: ToolParameterSpec[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const p of parameters) {
    if (p.default !== undefined && p.default !== null) {
      out[p.name] = p.default;
    } else if (p.type === "boolean") {
      out[p.name] = false;
    } else if (!p.required) {
      continue;
    } else if (p.type === "integer" || p.type === "number") {
      out[p.name] = 0;
    } else {
      out[p.name] = "";
    }
  }
  return out;
}

function ParamField({
  spec,
  value,
  onChange,
}: {
  spec: ToolParameterSpec;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = `${spec.name}${spec.required ? " *" : ""}`;
  const desc = spec.description ? (
    <span className="mt-0.5 block text-[10px] text-slate-500">{spec.description}</span>
  ) : null;

  if (spec.type === "boolean") {
    return (
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>
          {label}
          {desc}
        </span>
      </label>
    );
  }

  if (spec.enum?.length) {
    return (
      <label className="mb-3 block">
        <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
        {desc}
        <select
          className="input-field mt-1 w-full text-sm"
          value={String(value ?? spec.default ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">—</option>
          {spec.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (spec.type === "integer" || spec.type === "number") {
    return (
      <label className="mb-3 block">
        <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
        {desc}
        <input
          type="number"
          className="input-field mt-1 w-full text-sm"
          value={value === undefined || value === null ? "" : Number(value)}
          onChange={(e) =>
            onChange(
              spec.type === "integer"
                ? parseInt(e.target.value, 10) || 0
                : parseFloat(e.target.value) || 0,
            )
          }
        />
      </label>
    );
  }

  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {desc}
      <input
        className="input-field mt-1 w-full text-sm"
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

interface PlatformToolInspectorProps {
  data: Record<string, unknown>;
  catalog: ToolCatalogItem[];
  onPatch: (patch: Record<string, unknown>) => void;
}

export function PlatformToolInspector({
  data,
  catalog,
  onPatch,
}: PlatformToolInspectorProps) {
  const slug = String(data.tool_slug ?? "");
  const params = (data.params as Record<string, unknown>) ?? {};

  const tool = useMemo(
    () => catalog.find((t) => t.slug === slug),
    [catalog, slug],
  );

  const onSlugChange = (nextSlug: string) => {
    const next = catalog.find((t) => t.slug === nextSlug);
    const nextParams = next?.parameters?.length
      ? defaultParamsFromSpec(next.parameters)
      : {};
    onPatch({
      tool_slug: nextSlug,
      params: nextParams,
      confirmed: next?.require_confirmation ?? data.confirmed !== false,
    });
  };

  const setParam = (name: string, value: unknown) => {
    onPatch({ params: { ...params, [name]: value } });
  };

  const builtins = catalog.filter((t) => t.source === "builtin");
  const customs = catalog.filter((t) => t.source !== "builtin");

  return (
    <>
      <label className="mb-3 block">
        <span className="mb-1 block text-xs font-medium text-slate-600">工具</span>
        <select
          className="input-field w-full text-sm"
          value={slug}
          onChange={(e) => onSlugChange(e.target.value)}
        >
          <option value="">— 选择工具 —</option>
          {builtins.length > 0 && (
            <optgroup label="内置">
              {builtins.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name} ({t.slug})
                </option>
              ))}
            </optgroup>
          )}
          {customs.length > 0 && (
            <optgroup label="自定义">
              {customs.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name} ({t.slug})
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </label>
      {tool?.description && (
        <p className="mb-3 text-[11px] leading-relaxed text-slate-500">{tool.description}</p>
      )}
      {tool?.parameters && tool.parameters.length > 0 ? (
        <div className="mb-2 border-t border-slate-200 pt-2">
          <p className="mb-2 text-[10px] font-semibold uppercase text-slate-500">参数</p>
          {tool.parameters.map((spec) => (
            <ParamField
              key={spec.name}
              spec={spec}
              value={params[spec.name]}
              onChange={(v) => setParam(spec.name, v)}
            />
          ))}
        </div>
      ) : slug ? (
        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-medium text-slate-600">params (JSON)</span>
          <textarea
            className="input-field min-h-[72px] w-full font-mono text-xs"
            value={JSON.stringify(params, null, 2)}
            onChange={(e) => {
              try {
                onPatch({ params: JSON.parse(e.target.value || "{}") });
              } catch {
                /* 编辑中 */
              }
            }}
          />
        </label>
      ) : null}
      <p className="mb-2 text-[10px] text-amber-700">
        skill_* 工具需在绑定技能包的智能体对话或流程中执行。
      </p>
    </>
  );
}
