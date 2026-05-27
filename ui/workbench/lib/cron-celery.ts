/**
 * 标准 5 段 Cron 编辑/校验（链路 §10，与 Celery crontab、croniter 兼容）。
 * 用于智能体定时任务等 UI。
 */

export type CronParts = {
  minute: string;
  hour: string;
  dayOfMonth: string;
  month: string;
  dayOfWeek: string;
};

export const DEFAULT_CRON_PARTS: CronParts = {
  minute: "0",
  hour: "*",
  dayOfMonth: "*",
  month: "*",
  dayOfWeek: "*",
};

export type CronPreset = {
  label: string;
  parts: CronParts;
};

export const CRON_PRESETS: CronPreset[] = [
  { label: "每5分钟", parts: { minute: "*/5", hour: "*", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每10分钟", parts: { minute: "*/10", hour: "*", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每30分钟", parts: { minute: "*/30", hour: "*", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每小时整点", parts: { minute: "0", hour: "*", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每2小时", parts: { minute: "0", hour: "*/2", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每天零点", parts: { minute: "0", hour: "0", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每天早8点", parts: { minute: "0", hour: "8", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每天中午12点", parts: { minute: "0", hour: "12", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每天晚6点", parts: { minute: "0", hour: "18", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "每天晚10点", parts: { minute: "0", hour: "22", dayOfMonth: "*", month: "*", dayOfWeek: "*" } },
  { label: "工作日早8点", parts: { minute: "0", hour: "8", dayOfMonth: "*", month: "*", dayOfWeek: "1-5" } },
  { label: "工作日早9:30", parts: { minute: "30", hour: "9", dayOfMonth: "*", month: "*", dayOfWeek: "1-5" } },
  { label: "周末早10点", parts: { minute: "0", hour: "10", dayOfMonth: "*", month: "*", dayOfWeek: "0,6" } },
  { label: "周一早9点", parts: { minute: "0", hour: "9", dayOfMonth: "*", month: "*", dayOfWeek: "1" } },
  { label: "周五晚6点", parts: { minute: "0", hour: "18", dayOfMonth: "*", month: "*", dayOfWeek: "5" } },
  { label: "每月1号零点", parts: { minute: "0", hour: "0", dayOfMonth: "1", month: "*", dayOfWeek: "*" } },
  {
    label: "每季度第一天",
    parts: { minute: "0", hour: "0", dayOfMonth: "1", month: "1,4,7,10", dayOfWeek: "*" },
  },
];

export const MINUTE_OPTIONS = [
  { value: "0", label: "0分" },
  { value: "*/5", label: "每5分钟" },
  { value: "*/10", label: "每10分钟" },
  { value: "*/30", label: "每30分钟" },
  { value: "*", label: "每分钟" },
];

export const HOUR_OPTIONS = [
  { value: "*", label: "每小时" },
  { value: "*/2", label: "每2小时" },
  ...Array.from({ length: 24 }, (_, h) => ({
    value: String(h),
    label: `${String(h).padStart(2, "0")}时`,
  })),
];

export const DAY_OPTIONS = [
  { value: "*", label: "每天" },
  ...Array.from({ length: 31 }, (_, i) => ({
    value: String(i + 1),
    label: `${i + 1}日`,
  })),
];

export const MONTH_OPTIONS = [
  { value: "*", label: "每月" },
  ...Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1),
    label: `${i + 1}月`,
  })),
];

export const WEEK_OPTIONS = [
  { value: "*", label: "不指定" },
  { value: "1-5", label: "工作日" },
  { value: "0,6", label: "周末" },
  { value: "0", label: "周日" },
  { value: "1", label: "周一" },
  { value: "2", label: "周二" },
  { value: "3", label: "周三" },
  { value: "4", label: "周四" },
  { value: "5", label: "周五" },
  { value: "6", label: "周六" },
];

export function buildCronExpr(parts: CronParts): string {
  return [parts.minute, parts.hour, parts.dayOfMonth, parts.month, parts.dayOfWeek].join(" ");
}

export function parseCronExpr(expr: string): CronParts {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return { ...DEFAULT_CRON_PARTS };
  return {
    minute: parts[0] ?? "0",
    hour: parts[1] ?? "*",
    dayOfMonth: parts[2] ?? "*",
    month: parts[3] ?? "*",
    dayOfWeek: parts[4] ?? "*",
  };
}

export function validateCronExpr(expr: string): boolean {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  return parts.every((p) => p.length > 0);
}

export function describeCron(expr: string): string {
  const { minute, hour, dayOfMonth, month, dayOfWeek } = parseCronExpr(expr);

  if (minute.startsWith("*/") && hour === "*" && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return `每 ${minute.slice(2)} 分钟执行`;
  }
  if (minute === "0" && hour === "*" && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return "每小时整点执行";
  }
  if (minute === "0" && hour.startsWith("*/") && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return `每 ${hour.slice(2)} 小时执行`;
  }
  if (dayOfMonth === "*" && month === "*" && dayOfWeek === "1-5" && /^\d+$/.test(minute) && /^\d+$/.test(hour)) {
    return `工作日 ${hour.padStart(2, "0")}:${minute.padStart(2, "0")} 执行`;
  }
  if (dayOfMonth === "*" && month === "*" && dayOfWeek === "*" && /^\d+$/.test(minute) && /^\d+$/.test(hour)) {
    return `每天 ${hour.padStart(2, "0")}:${minute.padStart(2, "0")} 执行`;
  }
  if (dayOfMonth === "1" && month === "*" && dayOfWeek === "*" && minute === "0" && hour === "0") {
    return "每月 1 号零点执行";
  }
  if (month === "1,4,7,10" && dayOfMonth === "1" && dayOfWeek === "*" && minute === "0" && hour === "0") {
    return "每季度第一天零点执行";
  }

  const dowLabels: Record<string, string> = {
    "0": "周日",
    "1": "周一",
    "2": "周二",
    "3": "周三",
    "4": "周四",
    "5": "周五",
    "6": "周六",
  };
  if (dayOfMonth === "*" && month === "*" && dowLabels[dayOfWeek] && /^\d+$/.test(minute) && /^\d+$/.test(hour)) {
    return `每${dowLabels[dayOfWeek]} ${hour.padStart(2, "0")}:${minute.padStart(2, "0")} 执行`;
  }

  return `Cron: ${expr}`;
}

export function partsEqual(a: CronParts, b: CronParts): boolean {
  return (
    a.minute === b.minute &&
    a.hour === b.hour &&
    a.dayOfMonth === b.dayOfMonth &&
    a.month === b.month &&
    a.dayOfWeek === b.dayOfWeek
  );
}
