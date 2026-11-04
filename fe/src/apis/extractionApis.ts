import api from "@/axios";
import type { ApiResponse } from "@/interface/common/common.interface";
import type { ExtractedField, ExtractionRun, FieldFilters, FieldReview, ReviewPayload } from "@/interface/Extraction/Extraction.interface";

export async function getExtractionRuns(versionId: number, page = 1, signal?: AbortSignal) {
  return (await api.get<ApiResponse<ExtractionRun[]>>(`/backend/document-versions/${versionId}/extraction-runs`, { params: { page, itemsPerPage: 20 }, signal })).data;
}
export async function getExtractionRun(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<ExtractionRun>>(`/backend/extraction-runs/${id}`, { signal })).data;
}
export async function getExtractedFields(runId: number, params: FieldFilters, signal?: AbortSignal) {
  return (await api.get<ApiResponse<ExtractedField[]>>(`/backend/extraction-runs/${runId}/fields`, { params, signal })).data;
}
export async function createExtractionRun(versionId: number, idempotencyKey: string, signal?: AbortSignal) {
  return (await api.post<ApiResponse<ExtractionRun>>(`/backend/document-versions/${versionId}/extraction-runs`, { idempotency_key: idempotencyKey }, { signal })).data;
}
export async function retryExtractionRun(id: number, signal?: AbortSignal) {
  return (await api.post<ApiResponse<ExtractionRun>>(`/backend/extraction-runs/${id}/retry`, {}, { signal })).data;
}
export async function reviewField(id: number, payload: ReviewPayload) {
  return (await api.post<ApiResponse<ExtractedField>>(`/backend/extracted-fields/${id}/reviews`, payload)).data;
}
export async function getFieldReviews(id: number, page: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<FieldReview[]>>(`/backend/extracted-fields/${id}/reviews`, { params: { page, itemsPerPage: 5 }, signal })).data;
}
