import "server-only";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import type { ApiResponse } from "@/interface/common/common.interface";

export const SESSION_COOKIE = "regula_session";
const backend = (process.env.BACKEND_API_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export function backendFetch(path: string, init: RequestInit = {}, token?: string) {
  return fetch(`${backend}${path}`, {
    ...init, cache: "no-store", signal: AbortSignal.timeout(15000),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
}

export const isManager = (user: CurrentUser) => user.is_active &&
  user.roles.some((role) => role === "ADMIN" || role === "STAFF");

export async function readSession(): Promise<CurrentUser | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const response = await backendFetch("/auth/me", {}, token);
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("Authentication service is unavailable");
  const { data } = await response.json() as ApiResponse<CurrentUser>;
  return data && isManager(data) ? data : null;
}

export function jsonResponse(data: unknown, status = 200) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "private, no-store" } });
}

export function apiError(status: number, message: string) {
  return jsonResponse({ message, status_code: status, data: null, meta: null }, status);
}

export function sameOrigin(request: NextRequest) {
  const origin = request.headers.get("origin");
  return !origin || origin === request.nextUrl.origin;
}

export function clearSession(response: NextResponse) {
  response.cookies.set(SESSION_COOKIE, "", { path: "/", httpOnly: true, sameSite: "lax", maxAge: 0 });
  return response;
}
