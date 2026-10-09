"use client";
import { Spin } from "antd";
export default function LoadingScreen() {
  return <div className="loading-screen" role="status"><Spin size="large" /><p>Đang mở không gian làm việc…</p></div>;
}
