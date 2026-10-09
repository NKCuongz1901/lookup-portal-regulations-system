import { cookies } from "next/headers";
import { NextRequest } from "next/server";
import { apiError, backendFetch, clearSession, jsonResponse, SESSION_COOKIE } from "@/ultis/serverSession";

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
