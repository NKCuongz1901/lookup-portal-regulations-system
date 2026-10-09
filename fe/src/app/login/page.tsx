import { Suspense } from "react";
import { redirect } from "next/navigation";
import Login from "@/Container/Login";
import LoadingScreen from "@/Components/LoadingScreen/LoadingScreen";
import { readSession } from "@/ultis/serverSession";

export const metadata = { title: "Đăng nhập" };
async function LoginGate() {
  const user = await readSession().catch(() => null);
  if (user) redirect("/dashboard");
  return <Login />;
}
export default function LoginPage() {
  return <Suspense fallback={<LoadingScreen />}><LoginGate /></Suspense>;
}
