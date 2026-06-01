"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizClient } from "@/lib/types";

const INDUSTRY_LABELS: Record<string, string> = {
  government: "政府机关", enterprise: "企业", park: "园区",
  commercial: "商业综合体", tourism: "文旅", other: "其他",
};
const CONF_LABELS: Record<string, string> = {
  normal: "普通", internal: "内部", restricted: "涉密",
};

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [client, setClient] = useState<BizClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getClient(id)
      .then(setClient)
      .catch((e) => setError(e?.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !client) return <p className="text-sm text-red-600">{error || "客户不存在"}</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">
        ← 返回客户列表
      </button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{client.name}</h1>
          {client.short_name && <p className="text-sm text-ink-muted">{client.short_name}</p>}
        </div>
        <span className={`rounded px-2 py-0.5 text-xs ${
          client.confidentiality_level === "restricted" ? "bg-red-50 text-red-600" :
          client.confidentiality_level === "internal" ? "bg-yellow-50 text-yellow-700" :
          "bg-surface-muted text-ink-muted"
        }`}>
          {CONF_LABELS[client.confidentiality_level] ?? client.confidentiality_level}
        </span>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <InfoCard label="行业" value={INDUSTRY_LABELS[client.industry ?? ""] ?? client.industry ?? "—"} />
        <InfoCard label="项目数" value={`${client.project_count}`} />
        <InfoCard label="地址" value={client.address || "—"} />
        <InfoCard label="备注" value={client.remark || "—"} />
      </div>

      <div className="mt-8">
        <h2 className="text-sm font-semibold text-ink">联系人</h2>
        {client.contacts.length === 0 ? (
          <p className="mt-2 text-sm text-ink-faint">暂无联系人</p>
        ) : (
          <div className="mt-2 space-y-2">
            {client.contacts.map((c) => (
              <div key={c.id} className="card p-3 text-sm">
                <span className="font-medium text-ink">{c.name}</span>
                {c.is_primary && <span className="ml-2 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">主联系人</span>}
                {c.title && <span className="ml-2 text-ink-muted">{c.title}</span>}
                <div className="mt-1 text-xs text-ink-faint">
                  {c.phone && <span className="mr-3">{c.phone}</span>}
                  {c.email && <span>{c.email}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm text-ink">{value}</p>
    </div>
  );
}
