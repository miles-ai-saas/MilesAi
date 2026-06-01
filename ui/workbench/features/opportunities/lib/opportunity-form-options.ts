/** 商机表单选项（新建弹窗、详情编辑共用）。 */

import { OPPORTUNITY_STAGES } from "@/features/opportunities/lib/opportunity-labels";

export const OPPORTUNITY_CREATE_STAGES = OPPORTUNITY_STAGES.filter((s) => s.key !== "lost");

export type OpportunityFormValues = {
  client_id: string;
  name: string;
  stage: string;
  expected_value: string;
  probability: string;
  description: string;
};

export const EMPTY_OPPORTUNITY_FORM: OpportunityFormValues = {
  client_id: "",
  name: "",
  stage: "prospecting",
  expected_value: "",
  probability: "",
  description: "",
};
