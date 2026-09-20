"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type RateLimitRule } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";
import { EMPTY_RATE_LIMIT_RULE_FORM, type RateLimitRuleForm } from "@/features/risk/lib/risk-page-shared";

export function useRiskPage() {
  const ready = useRequireAdmin();
  const [newIp, setNewIp] = useState("");
  const [ipReason, setIpReason] = useState("");
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState<RateLimitRuleForm>(EMPTY_RATE_LIMIT_RULE_FORM);
  const [editRule, setEditRule] = useState<RateLimitRule | null>(null);
  const [editForm, setEditForm] = useState<RateLimitRuleForm>(EMPTY_RATE_LIMIT_RULE_FORM);
  const [ruleMsg, setRuleMsg] = useState("");
  const [ruleErr, setRuleErr] = useState("");

  const events = usePagedList(
    useCallback((p, s) => adminApi.listRiskEvents(p, s), []),
    { enabled: ready },
  );
  const ips = usePagedList(
    useCallback((p, s) => adminApi.listIpBlacklist(p, s), []),
    { enabled: ready },
  );
  const rules = usePagedList(
    useCallback((p, s) => adminApi.listRateLimits(p, s), []),
    { enabled: ready },
  );

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
        scope: ruleForm.scope,
        description: ruleForm.description.trim() || undefined,
      });
      setShowRuleForm(false);
      setRuleForm(EMPTY_RATE_LIMIT_RULE_FORM);
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
      scope: rule.scope,
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
        scope: editForm.scope,
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

  const onResolveEvent = async (eventId: string) => {
    await adminApi.resolveRisk(eventId);
    await events.reload();
  };

  const onAddIp = async () => {
    if (!newIp.trim()) return;
    await adminApi.addIp(newIp.trim(), ipReason || undefined);
    setNewIp("");
    setIpReason("");
    await ips.reload();
  };

  const onToggleIp = async (id: string, active: boolean) => {
    await adminApi.toggleIp(id, active);
    await ips.reload();
  };

  return {
    events,
    ips,
    rules,
    newIp,
    setNewIp,
    ipReason,
    setIpReason,
    showRuleForm,
    setShowRuleForm,
    ruleForm,
    setRuleForm,
    editRule,
    setEditRule,
    editForm,
    setEditForm,
    ruleMsg,
    ruleErr,
    onCreateRule,
    openEditRule,
    onSaveRule,
    onToggleRule,
    onResolveEvent,
    onAddIp,
    onToggleIp,
  };
}

export type RiskPageVm = ReturnType<typeof useRiskPage>;
