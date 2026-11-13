import api from "@/axios";
import { API_ROUTES } from "@/routes";
import type { CurrentUser, Role } from "@/interface/Auth/Auth.interface";
import type { ApiResponse, ListParams } from "@/interface/common/common.interface";

export type UserListParams = ListParams & {
  role?: Role;
};

export async function getUsers(params: UserListParams = {}, signal?: AbortSignal) {
  return (await api.get<ApiResponse<CurrentUser[]>>(API_ROUTES.users, { params, signal })).data;
}
