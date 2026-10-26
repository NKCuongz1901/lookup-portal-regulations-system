import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { ApiResponse } from "@/interface/common/common.interface";
import type { TagFilters, TagItem, TagPayload, TagUpdatePayload } from "@/interface/Tag/Tag.interface";

export async function listTags(params: TagFilters = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<TagItem[]>>(API_ROUTES.tags, { params, signal })).data;
}

export async function getTag(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<TagItem>>(`${API_ROUTES.tags}/${id}`, { signal })).data;
}

export async function createTag(payload: TagPayload) {
  return (await api.post<ApiResponse<TagItem>>(API_ROUTES.tags, payload)).data;
}

export async function updateTag(id: number, payload: TagUpdatePayload) {
  return (await api.patch<ApiResponse<TagItem>>(`${API_ROUTES.tags}/${id}`, payload)).data;
}
