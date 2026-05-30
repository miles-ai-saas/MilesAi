"use client";

type Point = { label: string; value: number };

type Props = {
  points: Point[];
  color?: string;
  className?: string;
  height?: number;
  /** 统计卡片等紧凑场景 */
  compact?: boolean;
  /** 占满父容器高度（趋势面板） */
  fill?: boolean;
  /** 日期轴渲染在绘图区下方 HTML 行，与折线对齐 */
  xLabelsBelow?: boolean;
};

const PAD_DEFAULT = { top: 8, right: 8, bottom: 22, left: 28 };
const PAD_COMPACT = { top: 6, right: 6, bottom: 18, left: 24 };
const PAD_FILL = { top: 12, right: 12, bottom: 8, left: 36 };

function niceMax(values: number[]): number {
  const max = Math.max(...values, 0);
  if (max <= 0) return 1;
  if (max <= 1) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(max)));
  const n = Math.ceil(max / exp);
  return (n <= 2 ? 2 : n <= 5 ? 5 : 10) * exp;
}

export function SimpleLineChart({
  points,
  color = "var(--brand)",
  className = "",
  height = 120,
  compact = false,
  fill = false,
  xLabelsBelow = false,
}: Props) {
  const PAD = fill ? PAD_FILL : compact ? PAD_COMPACT : PAD_DEFAULT;
  const width = fill ? 640 : compact ? 240 : 280;
  const plotHeight = fill ? 200 : height;
  const innerW = width - PAD.left - PAD.right;
  const innerH = plotHeight - PAD.top - PAD.bottom;
  const dotR = compact ? 2 : 3;
  const strokeW = compact ? 1.5 : 2;
  const fontSize = compact ? 8 : fill ? 10 : 9;
  const yMax = niceMax(points.map((p) => p.value));
  const n = Math.max(points.length, 1);

  const coords = points.map((p, i) => {
    const x = PAD.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = PAD.top + innerH - (p.value / yMax) * innerH;
    return { x, y, ...p, index: i };
  });

  const linePath = coords.length > 0 ? coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ") : "";

  const yTicks = [0, yMax * 0.5, yMax];
  const showEvery = points.length > 10 ? Math.ceil(points.length / 7) : 1;
  const visibleXLabels = coords.filter((c, i) => i % showEvery === 0 || i === coords.length - 1);

  const svg = (
    <svg
      viewBox={`0 0 ${width} ${plotHeight}`}
      preserveAspectRatio={fill ? "none" : undefined}
      className={fill ? "min-h-0 w-full flex-1" : `w-full max-w-full ${className}`}
      role="img"
      aria-hidden
    >
      {yTicks.map((tick) => {
        const y = PAD.top + innerH - (tick / yMax) * innerH;
        return (
          <g key={tick}>
            <line x1={PAD.left} y1={y} x2={width - PAD.right} y2={y} stroke="var(--line-soft, #f0f0f0)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y + 4} textAnchor="end" className="fill-ink-faint" fontSize={fontSize}>
              {tick % 1 === 0 ? tick : tick.toFixed(1)}
            </text>
          </g>
        );
      })}
      {linePath && <path d={linePath} fill="none" stroke={color} strokeWidth={strokeW} strokeLinejoin="round" strokeLinecap="round" />}
      {coords.map((c) => (
        <circle key={`${c.label}-${c.index}`} cx={c.x} cy={c.y} r={dotR} fill={color} />
      ))}
      {!xLabelsBelow &&
        coords.map((c, i) =>
          i % showEvery === 0 || i === coords.length - 1 ? (
            <text key={`${c.label}-x`} x={c.x} y={plotHeight - 4} textAnchor="middle" className="fill-ink-faint" fontSize={fontSize}>
              {c.label}
            </text>
          ) : null,
        )}
    </svg>
  );

  if (!xLabelsBelow) return svg;

  return (
    <div className={`flex h-full min-h-[220px] flex-col ${className}`}>
      {svg}
      <div
        className="relative mt-1 shrink-0 border-t border-line-soft pt-2"
        style={{ marginLeft: `${(PAD.left / width) * 100}%`, marginRight: `${(PAD.right / width) * 100}%`, height: "1.25rem" }}
      >
        {visibleXLabels.map((c) => {
          const leftPct = n === 1 ? 50 : (c.index / (n - 1)) * 100;
          return (
            <span
              key={`${c.label}-${c.index}`}
              className="absolute -translate-x-1/2 whitespace-nowrap text-[10px] text-ink-faint"
              style={{ left: `${leftPct}%` }}
            >
              {c.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
