"use client";

/** SubFlow 节点：选择已发布子流程与版本策略。 */

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Flow } from "@/lib/types";

type Props = {
  data: Record<string, unknown>;
  currentFlowId?: string;
  onChange: (patch: Record<string, unknown>) => void;
};

export function SubFlowInspector({ data, currentFlowId, onChange }: Props) {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .listFlows(1, 200)
      .then((page) => {
        setFlows(page.items.filter((f) => f.status === "published" && (!currentFlowId || f.id !== currentFlowId)));
      })
      .catch(() => setFlows([]))
      .finally(() => setLoading(false));
  }, [currentFlowId]);

  const selected = useMemo(() => flows.find((f) => f.id === String(data.sub_flow_id || "")), [flows, data.sub_flow_id]);

  const policy = String(data.version_policy || "published");

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-muted">子流程</span>
        <select
          className="input-field w-full text-sm"
          value={String(data.sub_flow_id || "")}
          onChange={(e) =>
            onChange({
              sub_flow_id: e.target.value,
              label: flows.find((f) => f.id === e.target.value)?.name || "子流程",
            })
          }
          disabled={loading}
        >
          <option value="">{loading ? "加载中…" : "选择已发布流程"}</option>
          {flows.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} · v{f.current_version}
            </option>
          ))}
        </select>
      </label>

      {selected ? (
        <p className="text-xs text-ink-faint">
          当前版本 v{selected.current_version} · {selected.description || "无描述"}
        </p>
      ) : null}

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-muted">版本策略</span>
        <select className="input-field w-full text-sm" value={policy} onChange={(e) => onChange({ version_policy: e.target.value })}>
          <option value="published">跟随已发布版</option>
          <option value="pinned">锁定指定版本</option>
        </select>
      </label>

      {policy === "pinned" ? (
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-muted">锁定版本号</span>
          <input
            type="number"
            min={1}
            className="input-field w-full text-sm"
            value={Number(data.pinned_version ?? 1)}
            onChange={(e) => onChange({ pinned_version: Number(e.target.value) || 1 })}
          />
        </label>
      ) : null}

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-muted">输出字段（可选）</span>
        <input
          className="input-field w-full text-sm"
          placeholder="留空则取子流程最终 output"
          value={String(data.output_key || "")}
          onChange={(e) => onChange({ output_key: e.target.value })}
        />
      </label>
    </div>
  );
}
