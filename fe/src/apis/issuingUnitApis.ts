import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { ApiResponse } from "@/interface/common/common.interface";
import type { IssuingUnit, IssuingUnitFilters, IssuingUnitPayload, IssuingUnitUpdatePayload } from "@/interface/IssuingUnit/IssuingUnit.interface";

export async function listIssuingUnits(params: IssuingUnitFilters = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<IssuingUnit[]>>(API_ROUTES.issuingUnits, { params, signal })).data;
}

export async function getIssuingUnit(id: number, signal?: AbortSignal) {
  return (await api.get<ApiResponse<IssuingUnit>>(`${API_ROUTES.issuingUnits}/${id}`, { signal })).data;
}

export async function createIssuingUnit(payload: IssuingUnitPayload) {
  return (await api.post<ApiResponse<IssuingUnit>>(API_ROUTES.issuingUnits, payload)).data;
}

export async function updateIssuingUnit(id: number, payload: IssuingUnitUpdatePayload) {
  return (await api.patch<ApiResponse<IssuingUnit>>(`${API_ROUTES.issuingUnits}/${id}`, payload)).data;
}
