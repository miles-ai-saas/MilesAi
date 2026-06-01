/** 新建项目表单（分步弹窗共用）。 */

export type WorkPackageDraft = {
  service_line: string;
  name: string;
};

export type ProjectFormValues = {
  client_id: string;
  name: string;
  code: string;
  description: string;
  work_packages: WorkPackageDraft[];
};

export const EMPTY_PROJECT_FORM: ProjectFormValues = {
  client_id: "",
  name: "",
  code: "",
  description: "",
  work_packages: [],
};
