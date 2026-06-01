"use client";

/** 兼容旧链接：重定向至商机列表（新建改为弹窗，保留 query）。 */

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function NewOpportunityRedirect() {
  const router = useRouter();
  const search = useSearchParams();

  useEffect(() => {
    const q = search.toString();
    router.replace(q ? `/business/opportunities?${q}` : "/business/opportunities");
  }, [router, search]);

  return null;
}

export default function NewOpportunityRedirectPage() {
  return (
    <Suspense fallback={null}>
      <NewOpportunityRedirect />
    </Suspense>
  );
}
