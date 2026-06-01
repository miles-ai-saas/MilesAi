/** 供应商表单选项（新建弹窗共用）。 */

import { SUPPLIER_CATEGORIES } from "@/features/suppliers/lib/supplier-labels";

export const SUPPLIER_STATUS_OPTIONS = [
  { value: "active", label: "合作中" },
  { value: "inactive", label: "暂停合作" },
  { value: "blacklisted", label: "黑名单" },
] as const;

export type SupplierFormValues = {
  name: string;
  short_name: string;
  category: string;
  status: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  address: string;
  bank_name: string;
  bank_account: string;
  remark: string;
};

export const EMPTY_SUPPLIER_FORM: SupplierFormValues = {
  name: "",
  short_name: "",
  category: "other",
  status: "active",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  address: "",
  bank_name: "",
  bank_account: "",
  remark: "",
};

export { SUPPLIER_CATEGORIES };
