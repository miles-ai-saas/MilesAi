import Link from "next/link";
import { CompanyLogo } from "./company-logo";

type Props = {
  href?: string;
  className?: string;
};

/** 侧栏 / 页头：仅展示「行千里」品牌文案。 */
export function BrandHeader({ href, className = "" }: Props) {
  const content = (
    <CompanyLogo variant="compact" size="sm" showTagline={false} className={`block min-w-0 ${className}`} />
  );

  if (href) {
    return (
      <Link href={href} className="flex shrink-0 items-center transition opacity-95 hover:opacity-100">
        {content}
      </Link>
    );
  }

  return <div className="flex shrink-0 items-center">{content}</div>;
}
