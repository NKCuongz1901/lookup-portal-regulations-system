import { NextRequest } from "next/server";
import { apiError, backendFetch, clearSession, isManager, jsonResponse, sameOrigin, SESSION_COOKIE } from "@/ultis/serverSession";
import type { CurrentUser, TokenResponse } from "@/interface/Auth/Auth.interface";
import type { ApiResponse } from "@/interface/common/common.interface";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  const body = await request.json().catch(() => null);
  if (!body || typeof body.email !== "string" || typeof body.password !== "string" ||
      !body.email.trim() || !body.password || (body.remember !== undefined && typeof body.remember !== "boolean")) {
    return apiError(422, "Email and password are required");
  }
  try {
    const loginResponse = await backendFetch("/auth/login", {
      method: "POST", body: JSON.stringify({ email: body.email.trim(), password: body.password }),
    });
    if (!loginResponse.ok) return clearSession(apiError(loginResponse.status, "Unable to sign in"));
    const { data: token } = await loginResponse.json() as ApiResponse<TokenResponse>;
    const meResponse = await backendFetch("/auth/me", {}, token.access_token);
    if (!meResponse.ok) return clearSession(apiError(meResponse.status, "Unable to verify account"));
    const { data: user } = await meResponse.json() as ApiResponse<CurrentUser>;
    if (!user || !isManager(user)) return clearSession(apiError(403, "Management access required"));
    const response = jsonResponse({ message: "Signed in", status_code: 200, data: user, meta: null });
    response.cookies.set(SESSION_COOKIE, token.access_token, {
      httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/",
      ...(body.remember ? { maxAge: token.expires_in } : {}),
    });
    return response;
  } catch {
    return apiError(503, "Authentication service unavailable");
  }
}
