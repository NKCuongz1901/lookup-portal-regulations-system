"use client";
import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import type { CurrentUser } from "@/interface/Auth/Auth.interface";

const AuthContext = createContext<CurrentUser | null>(null);
export function AuthProvider({ user, children }: { user: CurrentUser; children: ReactNode }) {
  return <AuthContext.Provider value={user}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const user = useContext(AuthContext);
  if (!user) throw new Error("useAuth must be used inside AuthProvider");
  return user;
}
