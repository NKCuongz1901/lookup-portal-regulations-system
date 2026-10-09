import { NextRequest } from "next/server";
import { apiError, clearSession, jsonResponse, sameOrigin } from "@/ultis/serverSession";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return apiError(403, "Invalid origin");
  return clearSession(jsonResponse({ message: "Signed out", status_code: 200, data: null, meta: null }));
}
