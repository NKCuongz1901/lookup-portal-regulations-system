"use client";
import { useState } from "react";
import { login } from "@/apis/authApis";
import { mainRoutes } from "@/routes/MainRoutes";
import type { LoginPayload } from "@/interface/Auth/Auth.interface";
import { requestError } from "@/ultis/requestError";

export default function useLogin() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function onLogin(values: LoginPayload) {
    setLoading(true); setError(null);
    try {
      await login(values);
      // Re-read the HttpOnly cookie in the protected server layout.
      window.location.replace(mainRoutes.dashboard);
    } catch (error) { setError(requestError(error)); setLoading(false); }
  }
  return { loading, error, onLogin, clearError: () => setError(null) };
}
