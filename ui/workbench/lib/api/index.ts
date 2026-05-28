/**
 * 租户 API 客户端（链路 §2，索引见 `lib/chains.ts`）。
 * 约定：`ApiResponse` 信封 `code===0` 才成功；分页走 `getPage` + `normalizePageResult`。
 */

import { agentsApi } from "./agents";
import { attachmentsApi } from "./attachments";
import { auditApi } from "./audit";
import { authApi } from "./auth";
import { complianceApi } from "./compliance";
import { flowsApi } from "./flows";
import { generativeApi } from "./generative";
import { hooksApi } from "./hooks";
import { kbApi } from "./kb";
import { marketplaceApi } from "./marketplace";
import { mcpApi } from "./mcp";
import { metaApi } from "./meta";
import { modelsApi } from "./models";
import { monitorApi } from "./monitor";
import { promptsApi } from "./prompts";
import { skillsApi } from "./skills";
import { systemApi } from "./system";
import { tagsApi } from "./tags";
import { tasksApi } from "./tasks";
import { toolsApi } from "./tools";
import { workbenchApi } from "./workbench";

export { getApiErrorMessage } from "../api-error";

export const api = {
  ...authApi,
  ...systemApi,
  ...monitorApi,
  ...auditApi,
  ...complianceApi,
  ...tagsApi,
  ...promptsApi,
  ...modelsApi,
  ...flowsApi,
  ...kbApi,
  ...agentsApi,
  ...attachmentsApi,
  ...generativeApi,
  ...metaApi,
  ...hooksApi,
  ...toolsApi,
  ...skillsApi,
  ...mcpApi,
  ...workbenchApi,
  ...tasksApi,
  ...marketplaceApi,
};
