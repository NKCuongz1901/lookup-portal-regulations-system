import { cookies } from "next/headers";
import { NextRequest } from "next/server";
import { apiError, backendFetch, clearSession, jsonResponse, sameOrigin, SESSION_COOKIE } from "@/ultis/serverSession";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!/^(users|documents(?:\/\d+)?|document-types|issuing-units|tags)$/.test(path)) {
    return apiError(404, "Not found");
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  try {
    const upstream = await backendFetch(`/${path}${request.nextUrl.search}`, {}, token);
    const response = jsonResponse(await upstream.json(), upstream.status);
    return upstream.status === 401 ? clearSession(response) : response;
  } catch {
    return apiError(503, "Backend unavailable");
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (path !== "documents") return apiError(404, "Not found");
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return apiError(415, "JSON content required");
  }
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) return apiError(422, "Invalid request body");
  try {
    const upstream = await backendFetch("/documents", { method: "POST", body: JSON.stringify(body) }, token);
    const response = jsonResponse(await upstream.json(), upstream.status);
    return upstream.status === 401 ? clearSession(response) : response;
  } catch {
    return apiError(503, "Backend unavailable");
  }
}
