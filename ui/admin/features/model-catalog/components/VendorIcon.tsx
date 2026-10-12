"use client";

/** 厂商图标：优先自定义 icon（URL），否则按 vendor 着色字标。 */

const VENDOR_STYLE: Record<string, { bg: string; fg: string; letter: string }> = {
  deepseek: { bg: "#e8f3ff", fg: "#1a6fb5", letter: "D" },
  doubao: { bg: "#fff0e8", fg: "#c45a1a", letter: "豆" },
  qwen: { bg: "#f0e8ff", fg: "#6b3fa0", letter: "Q" },
  openai: { bg: "#e8f8ef", fg: "#1a7f4b", letter: "O" },
  other: { bg: "#f1f1f3", fg: "#555", letter: "?" },
};

export function VendorIcon({
  vendor,
  icon,
  size = "md",
  className = "",
}: {
  vendor: string;
  icon?: string | null;
  size?: "sm" | "md";
  className?: string;
}) {
  const dim = size === "sm" ? "h-6 w-6 text-[10px]" : "h-8 w-8 text-xs";
  if (icon && /^https?:\/\//i.test(icon)) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={icon} alt="" className={`${dim} rounded-md object-cover ${className}`} />
    );
  }
  const style = VENDOR_STYLE[icon || vendor] || VENDOR_STYLE.other;
  return (
    <span
      className={`inline-flex ${dim} shrink-0 items-center justify-center rounded-md font-semibold ${className}`}
      style={{ backgroundColor: style.bg, color: style.fg }}
      title={vendor}
      aria-hidden
    >
      {style.letter}
    </span>
  );
}
