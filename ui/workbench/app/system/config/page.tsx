"use client";

/** 系统配置项（链路 §3，壳层 §7）。 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { PageHeader } from "@/components/layout/PageHeader";
import type { ConfigDefinition, InfraComponentStatus, InfraStatus } from "@/lib/types";

const PREVIEW_LABELS: Record<string, string> = {
  app_env: "运行环境",
  postgres: "PostgreSQL",
  redis: "Redis",
  object_storage_backend: "对象存储类型",
  object_storage_endpoint: "对象存储端点",
  object_storage_bucket: "存储桶",
  vector_store_backend: "向量库类型",
  vector_store_endpoint: "向量库端点",
  celery_broker: "Celery Broker",
  embedding_backend: "Embedding 后端",
};

function statusClass(status: InfraComponentStatus["status"]) {
  if (status === "ok") return "bg-emerald-50 text-emerald-800";
  if (status === "skipped") return "bg-surface-muted text-ink-faint";
  return "bg-amber-50 text-amber-800";
}

function statusLabel(status: InfraComponentStatus["status"]) {
  if (status === "ok") return "正常";
  if (status === "skipped") return "跳过";
  return "不可用";
}

export default function SystemConfigPage() {
  const { ready, user } = useRequireAuth();
  const [defs, setDefs] = useState<ConfigDefinition[]>([]);
  const [infra, setInfra] = useState<InfraStatus | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [testing, setTesting] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const reloadInfra = async () => {
    const status = await api.getInfraStatus();
    setInfra(status);
  };

  const reload = async () => {
    const d = await api.listConfigDefinitions();
    setDefs(d);
    await reloadInfra();
    const init: Record<string, string> = {};
    for (const item of d) {
      const v = item.default_value;
      init[item.key] = v == null ? "" : String(v);
    }
    setValues(init);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
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

  const onTestAll = async () => {
    setTesting(true);
    setTestingId(null);
    try {
      const res = await api.testInfraConnection();
      setInfra((prev) =>
        prev ? { ...prev, components: res.results, healthy: res.results.every((c) => c.status === "ok") } : prev,
      );
      setMsg("连接测试完成");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
    }
  };

  const onTestOne = async (componentId: string) => {
    setTesting(true);
    setTestingId(componentId);
    try {
      const res = await api.testInfraConnection([componentId]);
      const updated = res.results[0];
      if (updated) {
        setInfra((prev) =>
          prev
            ? {
                ...prev,
                components: prev.components.map((c) => (c.id === componentId ? updated : c)),
                healthy: prev.components
                  .map((c) => (c.id === componentId ? updated : c))
                  .every((c) => c.status === "ok"),
              }
            : prev,
        );
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
      setTestingId(null);
    }
  };

  const byCategory = defs.reduce<Record<string, ConfigDefinition[]>>((acc, d) => {
    (acc[d.category] ??= []).push(d);
    return acc;
  }, {});

  return (
    <div className="w-full space-y-6">
      <PageHeader
        title="系统配置"
        description="L2 业务参数可在此编辑；L1 部署连接（PostgreSQL / Redis / 对象存储等）来自环境变量，只读展示。"
      />

      {infra && (
        <section className="card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-ink">基础设施</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                部署级连接信息（脱敏）；修改请通过运维配置 .env / K8s Secret
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs ${
                  infra.healthy ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"
                }`}
              >
                {infra.healthy ? "全部正常" : "部分异常"}
              </span>
              {user?.is_superuser && (
                <button
                  type="button"
                  className="btn-ghost text-sm"
                  disabled={testing}
                  onClick={onTestAll}
                >
                  {testing && !testingId ? "测试中…" : "测试全部连接"}
                </button>
              )}
            </div>
          </div>

          <div className="mt-4 overflow-hidden rounded border border-line-soft">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="px-3 py-2">组件</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">耗时</th>
                  {user?.is_superuser && <th className="px-3 py-2 text-right">操作</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {infra.components.map((c) => (
                  <tr key={c.id}>
                    <td className="px-3 py-2">
                      <span className="font-medium text-ink">{c.label}</span>
                      {c.message && (
                        <p className="mt-0.5 text-xs text-ink-faint">{c.message}</p>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-2 py-0.5 text-xs ${statusClass(c.status)}`}>
                        {statusLabel(c.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-xs text-ink-muted">
                      {c.latency_ms != null ? `${c.latency_ms} ms` : "—"}
                    </td>
                    {user?.is_superuser && (
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          className="text-xs text-brand hover:underline disabled:opacity-50"
                          disabled={testing}
                          onClick={() => onTestOne(c.id)}
                        >
                          {testing && testingId === c.id ? "测试中…" : "测试"}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="mt-4 text-xs font-medium text-ink-muted">连接配置（脱敏）</h3>
          <ul className="mt-2 space-y-1 text-xs text-ink-muted">
            {Object.entries(infra.settings_preview).map(([k, v]) => (
              <li key={k}>
                <span className="text-ink-faint">{PREVIEW_LABELS[k] ?? k}:</span> {String(v ?? "—")}
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
