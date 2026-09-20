"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { RiskPageVm } from "@/features/risk/hooks/use-risk-page";
import { RATE_LIMIT_SCOPE_LABELS } from "@/features/risk/lib/risk-page-shared";

export function RiskRateLimitSection({ vm }: { vm: RiskPageVm }) {
  const { rules, showRuleForm, setShowRuleForm, ruleForm, setRuleForm, onCreateRule, openEditRule, onToggleRule } = vm;

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">限流配置</h2>
        <button type="button" className="btn-primary text-xs" onClick={() => setShowRuleForm((v) => !v)}>
          {showRuleForm ? "取消" : "新建规则"}
        </button>
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        路径支持通配符（如 <span className="cell-mono">/api/v1/auth/*</span>）。计量维度选「按来源 IP」走平台通用限流；选「按 API Key」用于 A2A
        等按对端计量的场景。
      </p>

      {showRuleForm && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <input className="input-field" placeholder="规则名称" value={ruleForm.name} onChange={(e) => setRuleForm((f) => ({ ...f, name: e.target.value }))} />
          <input
            className="input-field"
            placeholder="路径模式"
            value={ruleForm.path_pattern}
            onChange={(e) => setRuleForm((f) => ({ ...f, path_pattern: e.target.value }))}
          />
          <select className="input-field" value={ruleForm.scope} onChange={(e) => setRuleForm((f) => ({ ...f, scope: e.target.value as "ip" | "api_key" }))}>
            <option value="ip">按来源 IP</option>
            <option value="api_key">按 API Key</option>
          </select>
          <input
            className="input-field"
            type="number"
            min={1}
            placeholder="每分钟上限"
            value={ruleForm.limit_per_minute}
            onChange={(e) => setRuleForm((f) => ({ ...f, limit_per_minute: e.target.value }))}
          />
          <input
            className="input-field sm:col-span-2 lg:col-span-4"
            placeholder="说明（可选）"
            value={ruleForm.description}
            onChange={(e) => setRuleForm((f) => ({ ...f, description: e.target.value }))}
          />
          <button type="button" className="btn-primary sm:col-span-2 lg:col-span-1" onClick={() => void onCreateRule()}>
            保存规则
          </button>
        </div>
      )}

      {rules.loading ? (
        <p className="mt-3 text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="mt-4 admin-table-wrap border-0">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>路径</th>
                  <th>维度</th>
                  <th className="col-center col-numeric">上限</th>
                  <th className="col-center">状态</th>
                  <th className="col-actions">操作</th>
                </tr>
              </thead>
              <tbody>
                {rules.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center cell-muted">
                      暂无限流规则
                    </td>
                  </tr>
                )}
                {rules.items.map((r) => (
                  <tr key={r.id}>
                    <td className="cell-primary">{r.name}</td>
                    <td className="cell-mono cell-muted">{r.path_pattern}</td>
                    <td className="cell-muted">{RATE_LIMIT_SCOPE_LABELS[r.scope] ?? r.scope}</td>
                    <td className="col-center col-numeric cell-numeric">{r.limit_per_minute}/min</td>
                    <td className="col-center">
                      {r.is_active ? <span className="text-emerald-600">启用</span> : <span className="text-amber-600">停用</span>}
                    </td>
                    <td className="col-actions">
                      <button type="button" className="text-brand hover:underline" onClick={() => openEditRule(r)}>
                        编辑
                      </button>
                      <button type="button" className="text-ink-muted hover:underline" onClick={() => void onToggleRule(r)}>
                        {r.is_active ? "停用" : "启用"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ListFooter className="mt-3" page={rules.page} size={rules.size} total={rules.total} onPageChange={rules.setPage} onSizeChange={rules.setSize} />
        </>
      )}
    </section>
  );
}
