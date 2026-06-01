/** 客户表单下拉选项（列表、详情、新建弹窗共用）。 */

export const CLIENT_INDUSTRY_OPTIONS = [
  { value: "", label: "—" },
  { value: "government", label: "政府机关" },
  { value: "enterprise", label: "企业" },
  { value: "park", label: "园区" },
  { value: "commercial", label: "商业综合体" },
  { value: "tourism", label: "文旅" },
  { value: "other", label: "其他" },
] as const;

export const CLIENT_CONFIDENTIALITY_OPTIONS = [
  { value: "normal", label: "普通" },
  { value: "internal", label: "内部" },
  { value: "restricted", label: "涉密" },
] as const;

export type ClientFormValues = {
  name: string;
  short_name: string;
  industry: string;
  confidentiality_level: string;
  address: string;
  remark: string;
};

export const EMPTY_CLIENT_FORM: ClientFormValues = {
  name: "",
  short_name: "",
  industry: "",
  confidentiality_level: "normal",
  address: "",
  remark: "",
};
