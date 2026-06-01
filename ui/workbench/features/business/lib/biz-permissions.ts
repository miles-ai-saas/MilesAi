/** 业务中心 RBAC：读/写权限判断。 */

import { useAuthStore } from "@/lib/auth-store";
import { hasPermission } from "@/lib/permissions";

export type BizWriteDomain =
  | "client"
  | "opportunity"
  | "project"
  | "contract"
  | "payment"
  | "supplier";

const WRITE_CODES: Record<BizWriteDomain, string> = {
  client: "biz:client:write",
  opportunity: "biz:opportunity:write",
  project: "biz:project:write",
  contract: "biz:contract:write",
  payment: "biz:payment:write",
  supplier: "biz:supplier:write",
};

export function canBizWrite(domain: BizWriteDomain, user = useAuthStore.getState().user): boolean {
  return hasPermission(user, WRITE_CODES[domain]);
}

export function useBizPermissions() {
  const user = useAuthStore((s) => s.user);
  return {
    canWriteClient: canBizWrite("client", user),
    canWriteOpportunity: canBizWrite("opportunity", user),
    canWriteProject: canBizWrite("project", user),
    canWriteContract: canBizWrite("contract", user),
    canWritePayment: canBizWrite("payment", user),
    canWriteSupplier: canBizWrite("supplier", user),
  };
}
