"use client";

/** 定时任务编辑弹窗（链路 §10）。 */

import { useEffect, useMemo, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { api } from "@/lib/api";
import {
  CRON_PRESETS,
  DAY_OPTIONS,
  DEFAULT_CRON_PARTS,
  HOUR_OPTIONS,
  MINUTE_OPTIONS,
  MONTH_OPTIONS,
  WEEK_OPTIONS,
  buildCronExpr,
  describeCron,
  parseCronExpr,
  partsEqual,
  validateCronExpr,
  type CronParts,
} from "@/lib/cron-celery";
import type { AgentSchedule } from "@/lib/types";

const CONTENT_MAX = 500;

const CRON_FIELDS: {
  key: keyof CronParts;
  label: string;
  options: { value: string; label: string }[];
}[] = [
  { key: "minute", label: "分", options: MINUTE_OPTIONS },
  { key: "hour", label: "时", options: HOUR_OPTIONS },
  { key: "dayOfMonth", label: "日", options: DAY_OPTIONS },
  { key: "month", label: "月", options: MONTH_OPTIONS },
  { key: "dayOfWeek", label: "周", options: WEEK_OPTIONS },
];

function CronFieldPicker({ parts, onChange }: { parts: CronParts; onChange: (parts: CronParts) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {CRON_FIELDS.map(({ key, label, options }) => (
        <label key={key} className="block text-sm">
          <span className="mb-1 block text-ink-muted">{label}</span>
          <select className="input-field w-full" value={parts[key]} onChange={(e) => onChange({ ...parts, [key]: e.target.value })}>
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}

function CronExpressionPreview({ parts }: { parts: CronParts }) {
  const expr = buildCronExpr(parts);
  const description = describeCron(expr);

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-ink">Cron 表达式</p>
      <input readOnly value={expr} className="input-field w-full font-mono text-sm bg-surface-muted" aria-label="Cron 表达式" />
      <p className="text-xs text-ink-muted">{description}</p>
    </div>
  );
}

function CronPresetLinks({ parts, onSelect }: { parts: CronParts; onSelect: (parts: CronParts) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-ink-muted">常用</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {CRON_PRESETS.map((preset) => {
          const active = partsEqual(parts, preset.parts);
          return (
            <button
              key={preset.label}
              type="button"
              onClick={() => onSelect(preset.parts)}
              className={`text-xs transition hover:underline ${active ? "font-medium text-brand" : "text-brand"}`}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

type Props = {
  open: boolean;
  agentId: string;
  schedule?: AgentSchedule | null;
  onClose: () => void;
  onSaved: () => void;
};

export function AgentScheduleDialog({ open, agentId, schedule, onClose, onSaved }: Props) {
  const isEdit = Boolean(schedule);
  const [content, setContent] = useState("");
  const [cronParts, setCronParts] = useState<CronParts>(DEFAULT_CRON_PARTS);
  const [enabled, setEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const cronExpr = useMemo(() => buildCronExpr(cronParts), [cronParts]);
  const canSave = content.trim().length > 0 && validateCronExpr(cronExpr);

  useEffect(() => {
    if (!open) return;
    setError("");
    if (schedule) {
      setContent(schedule.content);
      setCronParts(parseCronExpr(schedule.cron));
      setEnabled(schedule.enabled);
    } else {
      setContent("");
      setCronParts(DEFAULT_CRON_PARTS);
      setEnabled(true);
    }
  }, [open, schedule]);

  const save = async () => {
    if (!canSave) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
        content: content.trim(),
        cron: cronExpr,
        enabled,
      };
      if (isEdit && schedule) {
        await api.updateAgentSchedule(agentId, schedule.id, payload);
      } else {
        await api.createAgentSchedule(agentId, payload);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title={isEdit ? "编辑定时任务" : "新建定时任务"}
      description="按计划向当前智能体发送消息"
      size="lg"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy || !canSave} onClick={() => void save()}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-ink">
            <span className="text-red-500">*</span> 触发消息
          </h3>
          <textarea
            className="input-field min-h-[100px] w-full resize-y"
            placeholder="任务触发后将作为用户消息发送给当前智能体"
            value={content}
            maxLength={CONTENT_MAX}
            onChange={(e) => setContent(e.target.value)}
          />
          <p className="text-right text-xs tabular-nums text-ink-faint">
            {content.length} / {CONTENT_MAX}
          </p>
        </section>

        <section className="space-y-3 rounded-xl border border-line-soft bg-surface-subtle/50 p-4">
          <div>
            <h3 className="text-sm font-medium text-ink">
              <span className="text-red-500">*</span> 执行计划
            </h3>
            <p className="mt-0.5 text-xs text-ink-faint">标准 5 段 Cron（分 时 日 月 周），最小粒度 1 分钟</p>
          </div>
          <CronFieldPicker parts={cronParts} onChange={setCronParts} />
          <CronExpressionPreview parts={cronParts} />
          <CronPresetLinks parts={cronParts} onSelect={setCronParts} />
        </section>

        <section className="flex items-center justify-between gap-4 rounded-xl border border-line-soft px-4 py-3">
          <div>
            <p className="text-sm font-medium text-ink">任务状态</p>
            <p className="mt-0.5 text-xs text-ink-faint">停用后 Beat 不再扫描该任务</p>
          </div>
          <ToggleSwitch checked={enabled} onChange={setEnabled} label={enabled ? "启用" : "停用"} />
        </section>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </ResourceDialog>
  );
}
