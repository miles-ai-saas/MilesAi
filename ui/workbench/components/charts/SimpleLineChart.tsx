"use client";

type Point = { label: string; value: number };

type Props = {
  points: Point[];
  color?: string;
  className?: string;
  height?: number;
  /** 统计卡片等紧凑场景 */
  compact?: boolean;
};

const PAD_DEFAULT = { top: 8, right: 8, bottom: 22, left: 28 };
const PAD_COMPACT = { top: 6, right: 6, bottom: 18, left: 24 };

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
}: Props) {
  const PAD = compact ? PAD_COMPACT : PAD_DEFAULT;
  const width = compact ? 240 : 280;
  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const dotR = compact ? 2 : 3;
  const strokeW = compact ? 1.5 : 2;
  const fontSize = compact ? 8 : 9;
  const yMax = niceMax(points.map((p) => p.value));
  const n = Math.max(points.length, 1);

  const coords = points.map((p, i) => {
    const x = PAD.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = PAD.top + innerH - (p.value / yMax) * innerH;
    return { x, y, ...p };
  });

  const linePath =
    coords.length > 0
      ? coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ")
      : "";

  const yTicks = [0, yMax * 0.5, yMax];
  const showEvery = points.length > 10 ? Math.ceil(points.length / 7) : 1;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`w-full max-w-full ${className}`}
      role="img"
      aria-hidden
    >
      {yTicks.map((tick) => {
        const y = PAD.top + innerH - (tick / yMax) * innerH;
        return (
          <g key={tick}>
            <line
              x1={PAD.left}
              y1={y}
              x2={width - PAD.right}
              y2={y}
              stroke="var(--line-soft, #f0f0f0)"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={y + 3}
              textAnchor="end"
              className="fill-ink-faint"
              fontSize={fontSize}
            >
              {tick % 1 === 0 ? tick : tick.toFixed(1)}
            </text>
          </g>
        );
      })}
      {linePath && (
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}
      {coords.map((c) => (
        <circle key={c.label} cx={c.x} cy={c.y} r={dotR} fill={color} />
      ))}
      {coords.map((c, i) =>
        i % showEvery === 0 || i === coords.length - 1 ? (
          <text
            key={`${c.label}-x`}
            x={c.x}
            y={height - 4}
            textAnchor="middle"
            className="fill-ink-faint"
            fontSize={fontSize}
          >
            {c.label}
          </text>
        ) : null,
      )}
    </svg>
  );
}
