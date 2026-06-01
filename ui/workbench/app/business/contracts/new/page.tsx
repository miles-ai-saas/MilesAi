"use client";

/** 兼容旧链接：重定向至合同列表（新建改为弹窗，保留 query）。 */

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function NewContractRedirect() {
  const router = useRouter();
  const search = useSearchParams();

  useEffect(() => {
    const q = search.toString();
    router.replace(q ? `/business/contracts?${q}` : "/business/contracts");
  }, [router, search]);

  return null;
}

export default function NewContractRedirectPage() {
  return (
    <Suspense fallback={null}>
      <NewContractRedirect />
    </Suspense>
  );
}
