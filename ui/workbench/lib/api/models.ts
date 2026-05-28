import type { ApiResponse, ModelCatalogMeta, ModelConfig } from "../types";
import { get, post, put, patch, http, unwrap } from "./client";

export const modelsApi = {
  getModelCatalogMeta: () => get<ModelCatalogMeta>("/models/meta"),

  listModelConfigs: (params?: { vendor?: string; model_type?: string; source?: "builtin" | "custom"; q?: string }) => {
    const q = new URLSearchParams();
    if (params?.vendor) q.set("vendor", params.vendor);
    if (params?.model_type) q.set("model_type", params.model_type);
    if (params?.source) q.set("source", params.source);
    if (params?.q) q.set("q", params.q);
    const qs = q.toString();
    return get<ModelConfig[]>(`/models${qs ? `?${qs}` : ""}`);
  },

  createModelConfig: (payload: {
    name: string;
    vendor?: string;
    provider?: string;
    model_name: string;
    model_code?: string;
    model_type?: string;
    description?: string;
    api_base?: string;
    api_key?: string;
  }) => post<ModelConfig>("/models", payload),

  updateModelConfig: (
    id: string,
    payload: {
      name?: string;
      vendor?: string;
      provider?: string;
      model_name?: string;
      model_code?: string;
      model_type?: string;
      description?: string;
      api_base?: string;
      api_key?: string;
      is_active?: boolean;
    },
  ) => patch<ModelConfig>(`/models/${id}`, payload),

  upsertBuiltinModelCredentials: (id: string, payload: { api_key: string; api_base?: string }) =>
    put<ModelConfig>(`/models/builtin/${id}/credentials`, payload),

  deleteBuiltinModelCredentials: async (id: string) => {
    const res = await http.delete<ApiResponse<ModelConfig>>(`/models/builtin/${id}/credentials`);
    return unwrap(res.data);
  },

  deleteModelConfig: (id: string) => http.delete(`/models/${id}`).then(() => undefined),
};
