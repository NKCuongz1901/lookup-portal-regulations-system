import { apiError, clearSession, jsonResponse, readSession } from "@/ultis/serverSession";

export async function GET() {
  try {
    const user = await readSession();
    return user ? jsonResponse({ message: "OK", status_code: 200, data: user, meta: null })
      : clearSession(apiError(401, "Session expired"));
  } catch {
    return apiError(503, "Authentication service unavailable");
  }
}
