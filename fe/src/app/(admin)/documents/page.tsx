import { Suspense } from "react";
import Documents from "@/Container/Documents";
import LoadingScreen from "@/Components/LoadingScreen/LoadingScreen";
export const metadata = { title: "Văn bản" };
export default function Page() { return <Suspense fallback={<LoadingScreen />}><Documents /></Suspense>; }
