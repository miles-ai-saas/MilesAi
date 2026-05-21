"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { PageHeader } from "@/components/layout/PageHeader";
import type { ConfigDefinition, RuntimeInfo } from "@/lib/types";

export default function SystemConfigPage() {
  const { ready } = useRequireAuth();
  const [defs, setDefs] = useState<ConfigDefinition[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");

  const reload = async () => {
    const [d, r] = await Promise.all([api.listConfigDefinitions(), api.getRuntimeInfo()]);
    setDefs(d);
    setRuntime(r);
    const init: Record<string, string> = {};
    for (const item of d) {
      const v = item.default_value;
      init[item.key] = v == null ? "" : String(v);
    }
    setValues(init);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready]);

  const onSave = async (key: string) => {
    setMsg("");
    const raw = values[key] ?? "";
    const num = Number(raw);
    const payload = Number.isFinite(num) && raw.trim() !== "" && /^-?\d+(\.\d+)?$/.test(raw.trim())
      ? num
      : raw;
    await api.upsertSystemConfig(key, payload);
    setMsg(`已保存 ${key}`);
    await reload();
  };

  const byCategory = defs.reduce<Record<string, ConfigDefinition[]>>((acc, d) => {
    (acc[d.category] ??= []).push(d);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="系统配置"
        description="业务参数与运行环境一览；敏感连接信息以环境变量为准，此处展示脱敏预览。"
      />

      {runtime && (
        <section className="card p-4">
          <h2 className="text-sm font-semibold text-ink">组件健康</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {Object.entries(runtime.components).map(([k, v]) => (
              <span
                key={k}
                className={`rounded px-2 py-1 ${
                  v === "ok" || v === "healthy"
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                {k}: {v}
              </span>
            ))}
          </div>
          <h3 className="mt-4 text-xs font-medium text-ink-muted">连接配置（脱敏）</h3>
          <ul className="mt-2 space-y-1 text-xs text-ink-muted">
            {Object.entries(runtime.settings_preview).map(([k, v]) => (
              <li key={k}>
                <span className="text-ink-faint">{k}:</span> {String(v ?? "—")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {Object.entries(byCategory).map(([cat, items]) => (
        <section key={cat} className="card p-4">
          <h2 className="text-sm font-semibold text-ink">{cat}</h2>
          <ul className="mt-4 space-y-4">
            {items.map((item) => (
              <li key={item.key}>
                <label className="block text-sm font-medium text-ink">{item.label}</label>
                <p className="text-xs text-ink-muted">{item.description}</p>
                <div className="mt-2 flex gap-2">
                  <input
                    className="input-field flex-1"
                    value={values[item.key] ?? ""}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [item.key]: e.target.value }))
                    }
                  />
                  <button
                    type="button"
                    className="btn-primary shrink-0"
                    onClick={() => onSave(item.key)}
                  >
                    保存
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {msg && <p className="text-sm text-ink-muted">{msg}</p>}
    </div>
  );
}
