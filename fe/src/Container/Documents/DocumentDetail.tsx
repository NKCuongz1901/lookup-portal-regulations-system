"use client";
import { useCallback, useState } from "react";
import { Alert, App, Button, Descriptions, Drawer, Skeleton, Space, Tabs, Tag } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { getDocument } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import StatusTag from "@/Components/StatusTag/StatusTag";
import { formatDate } from "@/ultis/format";
import DocumentVersions from "./DocumentVersions";
import DocumentForm from "./DocumentForm";
import ArchiveDocument from "./ArchiveDocument";
import type { DocumentDetail as DocumentDetailData } from "@/interface/Document/Document.interface";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function DocumentDetail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { message } = App.useApp();
  const [uploading, setUploading] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [updated, setUpdated] = useState<DocumentDetailData | null>(null);
  const loader = useCallback((signal: AbortSignal) => getDocument(id, signal), [id]);
  const { data, loading, error, reload } = useResource(loader);
  const doc = updated ?? (data?.data.id === id ? data.data : undefined);
  const busy = uploading || archiving || editing;
  return <Drawer title="Chi tiết văn bản" open onClose={() => { if (!busy) onClose(); }} size={640}
    closable={!busy} keyboard={!busy} mask={{ closable: !busy }}
    footer={doc && !loading && !error && <Space wrap>
      <Button type="primary" icon={<EditOutlined />} disabled={busy} onClick={() => setEditing(true)}>Sửa thông tin</Button>
      <ArchiveDocument document={doc} disabled={busy} onPendingChange={setArchiving} onArchived={(document) => {
        setUpdated(document); onChanged();
        void message.success(`Đã lưu trữ văn bản ${document.code}.`);
      }} />
    </Space>}>
    {loading ? <Skeleton active paragraph={{ rows: 10 }} /> : error ? <Alert type="error" title={error} action={<Button onClick={reload}>Thử lại</Button>} /> : doc && <>
      <div className={styles.detailHeading}><StatusTag status={doc.publication_status} /><h2>{doc.title}</h2><p>{doc.code}</p></div>
      <Tabs key={id} defaultActiveKey="information" destroyOnHidden items={[
        { key: "information", label: "Thông tin", disabled: busy, children: <Descriptions column={1} layout="vertical" items={[
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
        { key: "versions", label: "Phiên bản", disabled: archiving || editing, children: <DocumentVersions key={id} documentId={id} onUploadingChange={setUploading} /> },
      ]} />
    </>}
    {editing && doc && <DocumentForm key={doc.id} document={doc} onClose={() => setEditing(false)} onSaved={(document) => {
      setUpdated(document); setEditing(false); onChanged();
      void message.success(`Đã cập nhật văn bản ${document.code}.`);
    }} />}
  </Drawer>;
}
