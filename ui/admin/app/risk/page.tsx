"use client";

import { useCallback, useState } from "react";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type RateLimitRule } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const EMPTY_RULE_FORM = {
  name: "",
  path_pattern: "/api/v1/*",
  limit_per_minute: "60",
  description: "",
};

export default function RiskPage() {
  const ready = useRequireAdmin();
  const [newIp, setNewIp] = useState("");
  const [ipReason, setIpReason] = useState("");
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState(EMPTY_RULE_FORM);
  const [editRule, setEditRule] = useState<RateLimitRule | null>(null);
  const [editForm, setEditForm] = useState(EMPTY_RULE_FORM);
  const [ruleMsg, setRuleMsg] = useState("");
  const [ruleErr, setRuleErr] = useState("");

  const events = usePagedList(useCallback((p, s) => adminApi.listRiskEvents(p, s), []), {
    enabled: ready,
  });

  const ips = usePagedList(useCallback((p, s) => adminApi.listIpBlacklist(p, s), []), {
    enabled: ready,
  });

  const rules = usePagedList(useCallback((p, s) => adminApi.listRateLimits(p, s), []), {
    enabled: ready,
  });

  const onCreateRule = async () => {
    setRuleErr("");
    setRuleMsg("");
    if (!ruleForm.name.trim() || !ruleForm.path_pattern.trim()) {
      setRuleErr("请填写规则名称与路径模式");
      return;
    }
    try {
      await adminApi.createRateLimit({
        name: ruleForm.name.trim(),
        path_pattern: ruleForm.path_pattern.trim(),
        limit_per_minute: Number(ruleForm.limit_per_minute) || 60,
        description: ruleForm.description.trim() || undefined,
      });
      setShowRuleForm(false);
      setRuleForm(EMPTY_RULE_FORM);
      setRuleMsg("限流规则已创建");
      await rules.reload();
    } catch (e) {
      setRuleErr(e instanceof Error ? e.message : "创建失败");
    }
  };

  const openEditRule = (rule: RateLimitRule) => {
    setEditRule(rule);
    setEditForm({
      name: rule.name,
      path_pattern: rule.path_pattern,
      limit_per_minute: String(rule.limit_per_minute),
      description: rule.description ?? "",
    });
    setRuleErr("");
  };

  const onSaveRule = async () => {
    if (!editRule) return;
    setRuleErr("");
    try {
      await adminApi.updateRateLimit(editRule.id, {
        name: editForm.name.trim(),
        path_pattern: editForm.path_pattern.trim(),
        limit_per_minute: Number(editForm.limit_per_minute) || 60,
        description: editForm.description.trim() || null,
      });
      setEditRule(null);
      setRuleMsg("限流规则已更新");
      await rules.reload();
    } catch (e) {
      setRuleErr(e instanceof Error ? e.message : "更新失败");
    }
  };

  const onToggleRule = async (rule: RateLimitRule) => {
    setRuleErr("");
    try {
      await adminApi.updateRateLimit(rule.id, { is_active: !rule.is_active });
      setRuleMsg(rule.is_active ? "规则已停用" : "规则已启用");
      await rules.reload();
    } catch (e) {
      setRuleErr(e instanceof Error ? e.message : "操作失败");
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader title="风控管理" description="风险事件、IP 黑名单与 API 限流（私有化部署防护）" />

      {ruleMsg && <p className="text-sm text-emerald-600">{ruleMsg}</p>}
      {ruleErr && <p className="text-sm text-red-600">{ruleErr}</p>}

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">风险事件</h2>
        {events.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list mt-3">
              {events.items.length === 0 && <li className="text-ink-faint">暂无风险事件</li>}
              {events.items.map((e) => (
                <li key={e.id} className="admin-data-row flex items-center justify-between gap-2">
                  <span>
                    <span className="cell-primary">{e.event_type}</span>
                    <span className="cell-muted"> · {e.severity}</span>
                    {e.ip_address && <span className="admin-data-meta"> · {e.ip_address}</span>}
                    <span className="admin-data-meta ml-2">{e.created_at.slice(0, 19)}</span>
                  </span>
                  {!e.is_resolved ? (
                    <button
                      type="button"
                      className="text-xs text-brand hover:underline"
                      onClick={async () => {
                        await adminApi.resolveRisk(e.id);
                        await events.reload();
                      }}
                    >
                      标记已处理
                    </button>
                  ) : (
                    <span className="text-xs text-emerald-600">已处理</span>
                  )}
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={events.page}
              size={events.size}
              total={events.total}
              onPageChange={events.setPage}
              onSizeChange={events.setSize}
            />
          </>
        )}
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">IP 黑名单</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            className="input-field max-w-xs"
            placeholder="IP 地址"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
          />
          <input
            className="input-field max-w-xs"
            placeholder="封禁原因（可选）"
            value={ipReason}
            onChange={(e) => setIpReason(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary"
            onClick={async () => {
              if (!newIp.trim()) return;
              await adminApi.addIp(newIp.trim(), ipReason || undefined);
              setNewIp("");
              setIpReason("");
              await ips.reload();
            }}
          >
            封禁
          </button>
        </div>
        {ips.loading ? (
          <p className="mt-3 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
            <ul className="admin-data-list mt-3">
              {ips.items.length === 0 && <li className="text-ink-faint">暂无黑名单记录</li>}
              {ips.items.map((ip) => (
                <li key={ip.id} className="admin-data-row flex justify-between gap-2">
                  <span>
                    <span className="cell-mono">{ip.ip_address}</span>
                    {ip.reason && <span className="cell-muted"> — {ip.reason}</span>}
                    {!ip.is_active && <span className="text-amber-600"> (已禁用)</span>}
                  </span>
                  <button
                    type="button"
                    className="text-xs text-red-600 hover:underline"
                    onClick={async () => {
                      await adminApi.toggleIp(ip.id, !ip.is_active);
                      await ips.reload();
                    }}
                  >
                    {ip.is_active ? "禁用规则" : "启用规则"}
                  </button>
                </li>
              ))}
            </ul>
            <ListFooter
              className="mt-3"
              page={ips.page}
              size={ips.size}
              total={ips.total}
              onPageChange={ips.setPage}
              onSizeChange={ips.setSize}
            />
          </>
        )}
      </section>

      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">限流配置</h2>
          <button type="button" className="btn-primary text-xs" onClick={() => setShowRuleForm((v) => !v)}>
            {showRuleForm ? "取消" : "新建规则"}
          </button>
        </div>
        <p className="mt-1 text-xs text-ink-muted">
          路径支持通配符（如 <span className="cell-mono">/api/v1/auth/*</span>），命中后按 IP 滑动窗口限流。
        </p>

        {showRuleForm && (
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <input
              className="input-field"
              placeholder="规则名称"
              value={ruleForm.name}
              onChange={(e) => setRuleForm((f) => ({ ...f, name: e.target.value }))}
            />
            <input
              className="input-field"
              placeholder="路径模式"
              value={ruleForm.path_pattern}
              onChange={(e) => setRuleForm((f) => ({ ...f, path_pattern: e.target.value }))}
            />
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
            <button type="button" className="btn-primary sm:col-span-2 lg:col-span-1" onClick={onCreateRule}>
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
                    <th className="col-center col-numeric">上限</th>
                    <th className="col-center">状态</th>
                    <th className="col-actions">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center cell-muted">
                        暂无限流规则
                      </td>
                    </tr>
                  )}
                  {rules.items.map((r) => (
                    <tr key={r.id}>
                      <td className="cell-primary">{r.name}</td>
                      <td className="cell-mono cell-muted">{r.path_pattern}</td>
                      <td className="col-center col-numeric cell-numeric">{r.limit_per_minute}/min</td>
                      <td className="col-center">
                        {r.is_active ? (
                          <span className="text-emerald-600">启用</span>
                        ) : (
                          <span className="text-amber-600">停用</span>
                        )}
                      </td>
                      <td className="col-actions">
                        <button type="button" className="text-brand hover:underline" onClick={() => openEditRule(r)}>
                          编辑
                        </button>
                        <button type="button" className="text-ink-muted hover:underline" onClick={() => onToggleRule(r)}>
                          {r.is_active ? "停用" : "启用"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ListFooter
              className="mt-3"
              page={rules.page}
              size={rules.size}
              total={rules.total}
              onPageChange={rules.setPage}
              onSizeChange={rules.setSize}
            />
          </>
        )}
      </section>

      {editRule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="card w-full max-w-md p-4">
            <h3 className="font-semibold text-ink">编辑限流规则</h3>
            <div className="mt-3 grid gap-2">
              <input
                className="input-field"
                placeholder="规则名称"
                value={editForm.name}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              />
              <input
                className="input-field"
                placeholder="路径模式"
                value={editForm.path_pattern}
                onChange={(e) => setEditForm((f) => ({ ...f, path_pattern: e.target.value }))}
              />
              <input
                className="input-field"
                type="number"
                min={1}
                placeholder="每分钟上限"
                value={editForm.limit_per_minute}
                onChange={(e) => setEditForm((f) => ({ ...f, limit_per_minute: e.target.value }))}
              />
              <textarea
                className="input-field min-h-[72px] resize-y"
                placeholder="说明（可选）"
                value={editForm.description}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setEditRule(null)}>
                取消
              </button>
              <button type="button" className="btn-primary" onClick={onSaveRule}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
