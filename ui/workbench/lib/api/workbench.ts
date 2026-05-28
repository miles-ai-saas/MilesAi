import type { WorkbenchOverview } from "../types";
import { get } from "./client";

export const workbenchApi = {
  getWorkbenchOverview: () => get<WorkbenchOverview>("/workbench/overview"),

};
