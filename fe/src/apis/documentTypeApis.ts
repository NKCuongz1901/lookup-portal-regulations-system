import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { ApiResponse } from "@/interface/common/common.interface";
import type { DocumentType, DocumentTypeFilters, DocumentTypePayload, DocumentTypeUpdatePayload } from "@/interface/DocumentType/DocumentType.interface";

export async function listDocumentTypes(params: DocumentTypeFilters = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentType[]>>(API_ROUTES.documentTypes, { params, signal })).data;
}

export async function getDocumentType(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentType>>(`${API_ROUTES.documentTypes}/${id}`, { signal })).data;
}

export async function createDocumentType(payload: DocumentTypePayload) {
  return (await api.post<ApiResponse<DocumentType>>(API_ROUTES.documentTypes, payload)).data;
}

export async function updateDocumentType(id: number, payload: DocumentTypeUpdatePayload) {
  return (await api.patch<ApiResponse<DocumentType>>(`${API_ROUTES.documentTypes}/${id}`, payload)).data;
}
