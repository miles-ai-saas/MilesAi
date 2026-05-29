"use client";

import type { SystemConfigPageVm } from "@/features/system-config/hooks/use-system-config-page";

export function SystemConfigCategoriesSection({ vm }: { vm: SystemConfigPageVm }) {
  const { values, setValues, byCategory, onSave } = vm;

  return (
    <>
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
                    onChange={(e) => setValues((v) => ({ ...v, [item.key]: e.target.value }))}
                  />
                  <button type="button" className="btn-primary shrink-0" onClick={() => void onSave(item.key)}>
                    保存
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
