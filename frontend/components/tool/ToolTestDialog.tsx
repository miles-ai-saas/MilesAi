"use client";

/** 工具试调用（链路 §3，`api.invokeTool`）。 */
import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { ToolCatalogItem, ToolParameterSpec } from "@/lib/types";

type Props = {
  open: boolean;
  tool: ToolCatalogItem | null;
  onClose: () => void;
  onRun: (params: Record<string, unknown>, confirmed: boolean) => Promise<string>;
};

function defaultValue(spec: ToolParameterSpec): unknown {
  if (spec.default !== undefined && spec.default !== null) return spec.default;
  if (spec.type === "boolean") return false;
  if (spec.type === "integer" || spec.type === "number") return 0;
  return "";
}

export function ToolTestDialog({ open, tool, onClose, onRun }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const params = tool?.parameters ?? [];

  useEffect(() => {
    if (!open || !tool) return;
    const init: Record<string, unknown> = {};
    for (const p of tool.parameters ?? []) {
      init[p.name] = defaultValue(p);
    }
    setValues(init);
    setResult("");
    setNeedsConfirm(false);
  }, [open, tool]);

  const handleExecute = async (confirmed: boolean) => {
    if (!tool) return;
    setBusy(true);
    try {
      const text = await onRun(values, confirmed);
      if (text.startsWith("__CONFIRM__:")) {
        setNeedsConfirm(true);
        setResult(text.replace("__CONFIRM__:", ""));
      } else {
        setResult(text);
        setNeedsConfirm(false);
      }
    } catch (e) {
      setResult(e instanceof Error ? e.message : "调用失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title={tool ? `试调用 · ${tool.name}` : "试调用"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            关闭
          </button>
          {needsConfirm ? (
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => handleExecute(true)}
            >
              确认执行
            </button>
          ) : (
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => handleExecute(false)}
            >
              {busy ? "执行中…" : "执行"}
            </button>
          )}
        </>
      }
    >
      {params.length === 0 ? (
        <p className="text-xs text-ink-muted">此工具无输入参数，直接执行即可。</p>
      ) : (
        <div className="space-y-3">
          {params.map((p) => (
            <label key={p.name} className="block text-xs">
              <span className="mb-1 block text-ink-muted">
                {p.name}
                {p.required ? " *" : ""}
              </span>
              {p.type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={Boolean(values[p.name])}
                  onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.checked }))}
                />
              ) : (
                <input
                  className="input-field w-full"
                  value={String(values[p.name] ?? "")}
                  onChange={(e) => setValues((v) => ({ ...v, [p.name]: e.target.value }))}
                />
              )}
            </label>
          ))}
        </div>
      )}
      {needsConfirm && (
        <p className="mt-2 text-xs text-amber-700">此工具需要确认后才会真正执行。</p>
      )}
      {result && (
        <pre className="mt-3 max-h-48 overflow-auto rounded bg-surface-muted p-3 text-xs">{result}</pre>
      )}
    </ResourceDialog>
  );
}
