"use client";
import { useCallback, useState } from "react";
import { Alert, Button, Descriptions, Drawer, Skeleton, Tabs, Tag } from "antd";
import { getDocument } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import StatusTag from "@/Components/StatusTag/StatusTag";
import { formatDate } from "@/ultis/format";
import DocumentVersions from "./DocumentVersions";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function DocumentDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const [uploading, setUploading] = useState(false);
  const loader = useCallback((signal: AbortSignal) => getDocument(id, signal), [id]);
  const { data, loading, error, reload } = useResource(loader);
  const doc = data?.data.id === id ? data.data : undefined;
  return <Drawer title="Chi tiết văn bản" open onClose={() => { if (!uploading) onClose(); }} size={640}
    closable={!uploading} keyboard={!uploading} mask={{ closable: !uploading }}>
    {loading ? <Skeleton active paragraph={{ rows: 10 }} /> : error ? <Alert type="error" title={error} action={<Button onClick={reload}>Thử lại</Button>} /> : doc && <>
      <div className={styles.detailHeading}><StatusTag status={doc.publication_status} /><h2>{doc.title}</h2><p>{doc.code}</p></div>
      <Tabs key={id} defaultActiveKey="information" destroyOnHidden items={[
        { key: "information", label: "Thông tin", disabled: uploading, children: <Descriptions column={1} layout="vertical" items={[
        { key: "description", label: "Mô tả", children: doc.description || "Chưa có mô tả" },
        { key: "type", label: "Loại văn bản", children: doc.document_type?.name || "Chưa phân loại" },
        { key: "unit", label: "Đơn vị ban hành", children: doc.issuing_unit?.name || "Chưa thiết lập" },
        { key: "issue", label: "Ngày ban hành", children: formatDate(doc.issue_date) },
        { key: "from", label: "Có hiệu lực từ", children: formatDate(doc.effective_from) },
        { key: "until", label: "Có hiệu lực đến", children: formatDate(doc.effective_until) },
        { key: "year", label: "Năm học", children: doc.academic_year || "Chưa thiết lập" },
        { key: "subjects", label: "Đối tượng áp dụng", children: doc.applicable_subject_codes.length ? doc.applicable_subject_codes.map((code) => <Tag key={code}>{code}</Tag>) : "Chưa thiết lập" },
        { key: "tags", label: "Thẻ", children: doc.tags.length ? doc.tags.map((tag) => <Tag key={tag.id} color="blue">{tag.name}</Tag>) : "Chưa gắn thẻ" },
        { key: "created", label: "Ngày tạo", children: formatDate(doc.created_at) },
        { key: "updated", label: "Cập nhật lần cuối", children: formatDate(doc.updated_at) },
        ]} /> },
        { key: "versions", label: "Phiên bản", children: <DocumentVersions key={id} documentId={id} onUploadingChange={setUploading} /> },
      ]} />
    </>}
  </Drawer>;
}
