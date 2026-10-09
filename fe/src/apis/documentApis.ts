import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { DocumentDetail, DocumentFilters, DocumentItem, Lookup } from "@/interface/Document/Document.interface";
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
