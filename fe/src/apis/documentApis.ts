import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { DocumentCreatePayload, DocumentDetail, DocumentFilters, DocumentItem, DocumentTag, Lookup } from "@/interface/Document/Document.interface";
import type { ApiResponse } from "@/interface/common/common.interface";

export async function getDocuments(params: DocumentFilters = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentItem[]>>(API_ROUTES.documents, { params, signal })).data;
}
export async function getDocument(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentDetail>>(`${API_ROUTES.documents}/${id}`, { signal })).data;
}
export async function getDocumentTypes(signal?: AbortSignal) {
  return (await api.get<ApiResponse<Lookup[]>>(API_ROUTES.documentTypes, {
    params: { itemsPerPage: 100 }, signal,
  })).data;
}

export async function createDocument(payload: DocumentCreatePayload) {
  return (await api.post<ApiResponse<DocumentDetail>>(API_ROUTES.documents, payload)).data;
}

async function getAllOptions<T>(path: string, activeOnly: boolean, signal: AbortSignal) {
  const records: T[] = [];
  let page = 1;
  let totalPages = 1;
  do {
    const { data: response } = await api.get<ApiResponse<T[]>>(path, {
      params: { page, itemsPerPage: 100, ...(activeOnly ? { is_active: true } : {}) }, signal,
    });
    records.push(...response.data);
    totalPages = response.meta?.totalPages ?? 1;
    page += 1;
  } while (page <= totalPages);
  return records;
}

export async function getDocumentCreateOptions(signal: AbortSignal) {
  const [types, units, tags] = await Promise.all([
    getAllOptions<Lookup>(API_ROUTES.documentTypes, true, signal),
    getAllOptions<Lookup>(API_ROUTES.issuingUnits, true, signal),
    getAllOptions<DocumentTag>(API_ROUTES.tags, false, signal),
  ]);
  return { types, units, tags };
}
