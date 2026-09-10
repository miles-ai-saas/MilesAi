"use client";

import Link from "next/link";
import { STATUS_LABEL, statusBadgeClass, TYPE_LABEL, VENDOR_LABEL } from "@/features/model-catalog/lib/form-utils";
import { ListFooter } from "@/components/list/ListFooter";
import type { ModelCatalogPageVm } from "@/features/model-catalog/hooks/use-model-catalog-page";
import { MODEL_CATALOG_VENDOR_FILTERS } from "@/features/model-catalog/lib/model-catalog-page-shared";

export function ModelCatalogVendorFilterSection({ vm }: { vm: ModelCatalogPageVm }) {
  const { vendor, setVendor } = vm;

  return (
    <div className="admin-filter-bar">
      {MODEL_CATALOG_VENDOR_FILTERS.map((v) => (
        <button
          key={v || "all"}
          type="button"
          onClick={() => setVendor(v)}
          className={`admin-chip ${vendor === v ? "admin-chip-active" : ""}`}
        >
          {v ? (VENDOR_LABEL[v] ?? v) : "全部"}
        </button>
      ))}
    </div>
  );
}

export function ModelCatalogTableSection({ vm }: { vm: ModelCatalogPageVm }) {
  const { list } = vm;

  if (list.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th className="min-w-[10rem]">名称</th>
              <th className="col-compact">服务商</th>
              <th className="col-compact">类型</th>
              <th className="col-center">状态</th>
              <th className="col-center">平台 Key</th>
              <th className="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            {list.items.length === 0 && (
              <tr>
                <td colSpan={6} className="py-10 text-center cell-muted">
                  暂无模型。可{" "}
                  <Link href="/model-catalog/new" className="text-brand hover:underline">
                    新建
                  </Link>{" "}
                  或执行 seed。
                </td>
              </tr>
            )}
            {list.items.map((m) => {
              const modelId = m.model_code ?? m.model_name;
              return (
                <tr key={m.id}>
                  <td className="cell-stack">
                    <Link href={`/model-catalog/detail?id=${m.id}`} className="cell-stack-title hover:text-brand">
                      {m.name}
                    </Link>
                    {modelId && (
                      <div className="cell-stack-sub" title={modelId}>
                        {modelId}
                      </div>
                    )}
                  </td>
                  <td className="col-compact cell-muted whitespace-nowrap">{VENDOR_LABEL[m.vendor] ?? m.vendor}</td>
                  <td className="col-compact cell-muted whitespace-nowrap">{TYPE_LABEL[m.model_type] ?? m.model_type}</td>
                  <td className="col-center">
                    <span className={`status-badge ${statusBadgeClass(m.publish_status)}`}>{STATUS_LABEL[m.publish_status] ?? m.publish_status}</span>
                  </td>
                  <td className="col-center">
                    <span className={m.has_api_key ? "key-badge-ready" : "key-badge-missing"}>{m.has_api_key ? "已配置" : "未配置"}</span>
                  </td>
                  <td className="col-actions">
                    <Link href={`/model-catalog/detail?id=${m.id}`} className="text-brand hover:underline">
                      管理
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}
