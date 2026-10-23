import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { DocumentCreatePayload, DocumentDetail, DocumentDownload, DocumentFilters, DocumentItem, DocumentTag, DocumentUpdatePayload, DocumentVersion, DocumentVersionParams, Lookup } from "@/interface/Document/Document.interface";
import type { ApiResponse } from "@/interface/common/common.interface";
import { DOCUMENT_UPLOAD_TIMEOUT_MS } from "@/ultis/documentUpload";

export async function getDocuments(params: DocumentFilters = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentItem[]>>(API_ROUTES.documents, { params, signal })).data;
}
export async function getDocument(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentDetail>>(`${API_ROUTES.documents}/${id}`, { signal })).data;
}

export async function getDocumentVersions(id: number, params: DocumentVersionParams = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentVersion[]>>(`${API_ROUTES.documents}/${id}/versions`, { params, signal })).data;
}

export async function getDocumentDownload(id: number, versionId: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<DocumentDownload>>(`${API_ROUTES.documents}/${id}/download-url`, {
    params: { version_id: versionId }, signal,
  })).data;
}

export async function uploadDocumentVersion(
  id: number, file: File, onProgress?: (percent: number) => void, signal?: AbortSignal,
) {
  const body = new FormData();
  body.append("file", file);
  return (await api.post<ApiResponse<DocumentVersion>>(`${API_ROUTES.documents}/${id}/versions`, body, {
    signal, timeout: DOCUMENT_UPLOAD_TIMEOUT_MS + 60_000,
    onUploadProgress: (event) => {
      if (event.total) onProgress?.(Math.min(100, Math.round(event.loaded / event.total * 100)));
    },
  })).data;
}
export async function getDocumentTypes(signal?: AbortSignal) {
  return (await api.get<ApiResponse<Lookup[]>>(API_ROUTES.documentTypes, {
    params: { itemsPerPage: 100 }, signal,
  })).data;
}

export async function createDocument(payload: DocumentCreatePayload) {
  return (await api.post<ApiResponse<DocumentDetail>>(API_ROUTES.documents, payload)).data;
}

export async function updateDocument(id: number, payload: DocumentUpdatePayload) {
  return (await api.patch<ApiResponse<DocumentDetail>>(`${API_ROUTES.documents}/${id}`, payload)).data;
}

export async function archiveDocument(id: number) {
  return (await api.patch<ApiResponse<DocumentDetail>>(`${API_ROUTES.documents}/${id}/archive`)).data;
}

export async function deleteDocument(id: number) {
  return (await api.delete<ApiResponse<null>>(`${API_ROUTES.documents}/${id}`)).data;
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
