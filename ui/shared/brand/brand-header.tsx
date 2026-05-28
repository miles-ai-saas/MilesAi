import Link from "next/link";
import { CompanyLogo } from "./company-logo";

type Props = {
  productLine: string;
  href?: string;
  className?: string;
};

/** 侧栏 / 页头：公司 Logo + 产品线说明 */
export function BrandHeader({ productLine, href, className = "" }: Props) {
  const content = (
    <div className={`min-w-0 leading-tight ${className}`}>
      <CompanyLogo variant="compact" size="sm" showTagline={false} className="block" />
      <p className="truncate text-[11px] font-medium text-ink-muted">{productLine}</p>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="shrink-0 transition opacity-95 hover:opacity-100">
        {content}
      </Link>
    );
  }

  return <div className="shrink-0">{content}</div>;
}
