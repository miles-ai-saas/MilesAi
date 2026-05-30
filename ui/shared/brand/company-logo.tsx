import type { SVGProps } from "react";

/** 公司品牌色（行千里 Logo） */
export const COMPANY_ORANGE = "#E66432";
export const COMPANY_TAGLINE = "#C9A88E";

export type CompanyLogoVariant = "full" | "compact" | "mark";
export type CompanyLogoSize = "sm" | "md" | "lg";

const SIZE: Record<
  CompanyLogoSize,
  { width: number; height: number; title: number; tag: number; gap: number }
> = {
  sm: { width: 108, height: 34, title: 22, tag: 7, gap: 4 },
  md: { width: 148, height: 46, title: 30, tag: 8, gap: 5 },
  lg: { width: 220, height: 68, title: 44, tag: 10, gap: 6 },
};

type Props = SVGProps<SVGSVGElement> & {
  variant?: CompanyLogoVariant;
  size?: CompanyLogoSize;
  showTagline?: boolean;
};

function LogoText({
  titleSize,
  tagSize,
  gap,
  showTagline,
}: {
  titleSize: number;
  tagSize: number;
  gap: number;
  showTagline: boolean;
}) {
  const titleY = titleSize * 0.88;
  const tagY = titleY + gap + tagSize;
  return (
    <>
      <text
        x="50%"
        y={titleY}
        textAnchor="middle"
        fill={COMPANY_ORANGE}
        style={{
          fontSize: titleSize,
          fontWeight: 700,
          fontFamily:
            '"PingFang SC", "Noto Sans SC", "Microsoft YaHei", "Helvetica Neue", sans-serif',
          letterSpacing: "0.06em",
        }}
      >
        行千里
      </text>
      {showTagline ? (
        <text
          x="50%"
          y={tagY}
          textAnchor="middle"
          fill={COMPANY_TAGLINE}
          style={{
            fontSize: tagSize,
            fontWeight: 500,
            fontFamily:
              '"Segoe UI", "Helvetica Neue", system-ui, -apple-system, sans-serif',
            letterSpacing: "0.32em",
          }}
        >
          — NO STEP NO MILE —
        </text>
      ) : null}
    </>
  );
}

/** 公司 Logo：行千里 + NO STEP NO MILE */
export function CompanyLogo({
  variant = "full",
  size = "md",
  showTagline,
  className,
  ...props
}: Props) {
  const dim = SIZE[size];
  const tagline =
    showTagline ?? (variant === "full" || (variant === "compact" && size !== "sm"));

  if (variant === "mark") {
    const box = size === "sm" ? 32 : size === "md" ? 36 : 40;
    return (
      <svg
        width={box}
        height={box}
        viewBox={`0 0 ${box} ${box}`}
        role="img"
        aria-label="行千里"
        className={className}
        {...props}
      >
        <rect width={box} height={box} rx={8} fill="#FEF3EE" />
        <text
          x="50%"
          y={box * 0.68}
          textAnchor="middle"
          fill={COMPANY_ORANGE}
          style={{
            fontSize: box * 0.26,
            fontWeight: 700,
            fontFamily: '"PingFang SC", "Noto Sans SC", sans-serif',
            letterSpacing: "-0.06em",
          }}
        >
          行千里
        </text>
      </svg>
    );
  }

  const height = tagline ? dim.height : dim.title + 6;

  return (
    <svg
      width={dim.width}
      height={height}
      viewBox={`0 0 ${dim.width} ${height}`}
      role="img"
      aria-label="行千里"
      className={className}
      {...props}
    >
      <LogoText
        titleSize={dim.title}
        tagSize={dim.tag}
        gap={dim.gap}
        showTagline={tagline}
      />
    </svg>
  );
}
