import { cookies } from "next/headers";
import { NextRequest } from "next/server";
import { apiError, backendFetch, clearSession, jsonResponse, sameOrigin, SESSION_COOKIE } from "@/ultis/serverSession";
import { DOCUMENT_UPLOAD_TIMEOUT_MS } from "@/ultis/documentUpload";
import { readDocumentUpload, UploadValidationError } from "@/ultis/serverUpload";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!/^(users|documents(?:\/\d+(?:\/(?:versions|download-url))?)?|document-types(?:\/[1-9]\d*)?|issuing-units|tags)$/.test(path)) {
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

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!/^documents\/[1-9]\d*$/.test(path)) return apiError(404, "Not found");
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  try {
    const upstream = await backendFetch(`/${path}`, { method: "DELETE" }, token);
    const response = jsonResponse(await upstream.json(), upstream.status);
    return upstream.status === 401 ? clearSession(response) : response;
  } catch {
    return apiError(503, "Backend unavailable");
  }
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!/^(documents\/[1-9]\d*(?:\/archive)?|document-types\/[1-9]\d*)$/.test(path)) return apiError(404, "Not found");
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  let body: string | undefined;
  if (!path.endsWith("/archive")) {
    if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
      return apiError(415, "JSON content required");
    }
    const payload: unknown = await request.json().catch(() => null);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return apiError(422, "Invalid request body");
    body = JSON.stringify(payload);
  }
  try {
    const upstream = await backendFetch(`/${path}`, { method: "PATCH", body }, token);
    const response = jsonResponse(await upstream.json(), upstream.status);
    return upstream.status === 401 ? clearSession(response) : response;
  } catch {
    return apiError(503, "Backend unavailable");
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const isUpload = /^documents\/\d+\/versions$/.test(path);
  if (path !== "documents" && path !== "document-types" && !isUpload) return apiError(404, "Not found");
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  if (isUpload) {
    try {
      const body = await readDocumentUpload(request);
      const upstream = await backendFetch(`/${path}`, {
        method: "POST", body, signal: AbortSignal.timeout(DOCUMENT_UPLOAD_TIMEOUT_MS),
      }, token);
      const response = jsonResponse(await upstream.json(), upstream.status);
      return upstream.status === 401 ? clearSession(response) : response;
    } catch (error) {
      if (error instanceof UploadValidationError) return apiError(error.status, error.message);
      if (error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name)) {
        return apiError(504, "Upload result unknown. Refresh versions before retrying.");
      }
      return apiError(503, "Upload result unknown. Refresh versions before retrying.");
    }
  }
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return apiError(415, "JSON content required");
  }
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) return apiError(422, "Invalid request body");
  try {
    const upstream = await backendFetch(`/${path}`, { method: "POST", body: JSON.stringify(body) }, token);
    const response = jsonResponse(await upstream.json(), upstream.status);
    return upstream.status === 401 ? clearSession(response) : response;
  } catch {
    return apiError(503, "Backend unavailable");
  }
}
