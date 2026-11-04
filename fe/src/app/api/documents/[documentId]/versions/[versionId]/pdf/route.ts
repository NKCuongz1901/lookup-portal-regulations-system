import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { apiError, backendFetch, clearSession, jsonResponse, SESSION_COOKIE } from "@/ultis/serverSession";
import type { DocumentDownload } from "@/interface/Document/Document.interface";
import { DOCUMENT_MAX_FILE_SIZE } from "@/ultis/documentUpload";

export const runtime = "nodejs";

// The client supplies record IDs, never a destination URL. The backend checks
// ADMIN/STAFF access and signs the exact version on every request.
export async function GET(request: NextRequest, context: { params: Promise<{ documentId: string; versionId: string }> }) {
  const { documentId, versionId } = await context.params;
  if (![documentId, versionId].every((id) => /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)))) return apiError(404, "Not found");
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return apiError(401, "Authentication required");
  try {
    const signed = await backendFetch(`/documents/${documentId}/download-url?version_id=${versionId}`, {}, token);
    const payload = await signed.json();
    if (!signed.ok) {
      const response = jsonResponse(payload, signed.status);
      return signed.status === 401 ? clearSession(response) : response;
    }
    const file = payload.data as DocumentDownload;
    if (file.document_id !== Number(documentId) || file.version_id !== Number(versionId)) return apiError(502, "Invalid file response");
    if (file.mime_type !== "application/pdf") return apiError(415, "Only PDF preview is supported");
    if (!Number.isFinite(file.size_bytes) || file.size_bytes <= 0 || file.size_bytes > DOCUMENT_MAX_FILE_SIZE) return apiError(413, "PDF exceeds preview size limit");
    const url = new URL(file.url);
    if (url.protocol !== "https:" || !url.hostname.endsWith(".r2.cloudflarestorage.com") || url.username || url.password || url.port) return apiError(502, "Invalid storage destination");
    const upstream = await fetch(url, {
      redirect: "error", cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(120_000)]),
    });
    if (!upstream.ok || !upstream.body) return apiError(502, "PDF could not be loaded from storage");
    return new Response(upstream.body, { headers: {
      "Content-Type": "application/pdf", "Content-Disposition": "inline",
      "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch { return apiError(503, "PDF preview unavailable. Please retry."); }
}
