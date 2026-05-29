"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import type { Role } from "@/lib/types";

export function useSystemUsersList() {
  const { ready, user: currentUser } = useRequireAuth();
  const list = usePagedList(useCallback((p, s) => api.listUsers(p, s), []), { enabled: ready });
  const [roles, setRoles] = useState<Role[]>([]);

  useEffect(() => {
    if (!ready) return;
    void api.listAssignableRoles().then(setRoles);
  }, [ready]);

  return { currentUser, list, roles };
}
