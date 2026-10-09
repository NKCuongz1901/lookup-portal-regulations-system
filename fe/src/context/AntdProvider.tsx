"use client";
import { App, ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import type { ReactNode } from "react";

export default function AntdProvider({ children }: { children: ReactNode }) {
  return <ConfigProvider locale={viVN} theme={{
    token: {
      colorPrimary: "#2467db", colorSuccess: "#299779", colorText: "#182230",
      colorTextSecondary: "#818a98", colorBorder: "#e5e9f0", colorBgLayout: "#f7f9fc",
      fontFamily: "var(--font-geist), Arial, sans-serif", fontSize: 14,
      borderRadius: 8, controlHeight: 42,
    },
    components: {
      Button: { primaryShadow: "none", fontWeight: 500 },
      Table: { headerBg: "#f8fafc", headerColor: "#7a8494", cellPaddingBlock: 18 },
      Menu: { itemHeight: 50, itemSelectedBg: "#edf4ff", itemSelectedColor: "#2467db" },
    },
  }}><App>{children}</App></ConfigProvider>;
}
