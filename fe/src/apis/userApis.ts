import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import type { ApiResponse, ListParams } from "@/interface/common/common.interface";

export async function getUsers(params: ListParams = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<CurrentUser[]>>(API_ROUTES.users, { params, signal })).data;
}
