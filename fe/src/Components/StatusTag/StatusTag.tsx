"use client";
import { Tag } from "antd";
import type { PublicationStatus } from "@/interface/Document/Document.interface";
export const publicationLabels: Record<PublicationStatus, string> = {
  draft: "Bản nháp", published: "Đã công bố", hidden: "Đã ẩn", archived: "Lưu trữ",
};
export const publicationColors: Record<PublicationStatus, string> = {
  draft: "#df9c35", published: "#299779", hidden: "#8193b0", archived: "#a5acb7",
};
export default function StatusTag({ status }: { status: PublicationStatus }) {
  return <Tag className="status-tag" variant="filled" color={status === "published" ? "success" : status === "draft" ? "warning" : "default"}>
    <span style={{ background: publicationColors[status] }} />{publicationLabels[status]}
  </Tag>;
}
