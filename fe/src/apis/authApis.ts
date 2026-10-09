import api from "@/axios";
import { AUTH_ROUTES } from "@/routes";
import type { CurrentUser, LoginPayload } from "@/interface/Auth/Auth.interface";
import type { ApiResponse } from "@/interface/common/common.interface";

export async function login(payload: LoginPayload) {
  return (await api.post<ApiResponse<CurrentUser>>(AUTH_ROUTES.login, payload)).data;
}
export async function logout() {
  await api.post(AUTH_ROUTES.logout);
}
