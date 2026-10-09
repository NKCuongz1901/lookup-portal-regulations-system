import { Suspense } from "react";
import { redirect } from "next/navigation";
import AdminLayout from "@/Container/AdminLayout";
import { AuthProvider } from "@/context/AuthContext";
import LoadingScreen from "@/Components/LoadingScreen/LoadingScreen";
import { readSession } from "@/ultis/serverSession";

async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const user = await readSession();
  if (!user) redirect("/login");
  return <AuthProvider user={user}><AdminLayout>{children}</AdminLayout></AuthProvider>;
}
export default function Layout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingScreen />}><ProtectedLayout>{children}</ProtectedLayout></Suspense>;
}
