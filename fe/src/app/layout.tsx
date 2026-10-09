import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import AntdProvider from "@/context/AntdProvider";
import "antd/dist/reset.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Regula — Quản trị văn bản", template: "%s | Regula" },
  description: "Không gian quản trị người dùng, văn bản và quy định của đơn vị.",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="vi"><body><AntdRegistry><AntdProvider>{children}</AntdProvider></AntdRegistry></body></html>;
}
