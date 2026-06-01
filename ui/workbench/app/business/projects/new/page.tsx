"use client";

/** 兼容旧链接：重定向至项目列表并打开新建弹窗（`?create=1`，保留其他 query）。 */

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function NewProjectRedirect() {
  const router = useRouter();
  const search = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams(search.toString());
    params.set("create", "1");
    router.replace(`/business/projects?${params.toString()}`);
  }, [router, search]);

  return null;
}

export default function NewProjectRedirectPage() {
  return (
    <Suspense fallback={null}>
      <NewProjectRedirect />
    </Suspense>
  );
}
