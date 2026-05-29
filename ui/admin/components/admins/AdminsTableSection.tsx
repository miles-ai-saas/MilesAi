"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { AdminsPageVm } from "@/hooks/use-admins-page";

export function AdminsTableSection({ vm }: { vm: AdminsPageVm }) {
  const { list, currentId, setResetId, onDisable } = vm;

  return (
    <section className="card p-4">
      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="admin-table-wrap border-0">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>用户名</th>
                  <th>显示名</th>
                  <th className="col-center">角色</th>
                  <th className="col-center">状态</th>
                  <th className="col-actions">操作</th>
                </tr>
              </thead>
              <tbody>
                {list.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-10 text-center cell-muted">
                      暂无管理员
                    </td>
                  </tr>
                )}
                {list.items.map((a) => (
                  <tr key={a.id}>
                    <td className="cell-primary">{a.username}</td>
                    <td className="cell-muted">{a.display_name || "—"}</td>
                    <td className="col-center">
                      <span className="badge bg-brand-light text-ink">{a.role}</span>
                    </td>
                    <td className="col-center">
                      {a.is_active ? <span className="text-emerald-600">启用</span> : <span className="text-ink-faint">已禁用</span>}
                    </td>
                    <td className="col-actions">
                      {a.is_active && (
                        <button type="button" className="text-brand hover:underline" onClick={() => setResetId(a.id)}>
                          重置密码
                        </button>
                      )}
                      {a.is_active && a.id !== currentId && (
                        <button type="button" className="text-red-600 hover:underline" onClick={() => void onDisable(a.id)}>
                          禁用
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        </>
      )}
    </section>
  );
}
