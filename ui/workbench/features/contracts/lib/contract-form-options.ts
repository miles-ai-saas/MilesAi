/** 合同表单选项（新建弹窗共用）。 */

export const CONTRACT_TYPE_OPTIONS = [
  { value: "service", label: "服务合同" },
  { value: "nda", label: "保密协议" },
  { value: "framework", label: "框架协议" },
  { value: "other", label: "其他" },
] as const;

export type ContractFormValues = {
  project_id: string;
  client_id: string;
  name: string;
  contract_no: string;
  type: string;
  total_amount: string;
  payment_terms: string;
  description: string;
};

export const EMPTY_CONTRACT_FORM: ContractFormValues = {
  project_id: "",
  client_id: "",
  name: "",
  contract_no: "",
  type: "service",
  total_amount: "",
  payment_terms: "",
  description: "",
};
