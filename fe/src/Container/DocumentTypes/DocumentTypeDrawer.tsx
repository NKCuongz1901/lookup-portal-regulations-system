"use client";
import { useCallback } from "react";
import { Alert, Button, Descriptions, Drawer, Skeleton, Tag } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { getDocumentType } from "@/apis/documentTypeApis";
import useResource from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import { canManageDocumentTypes } from "@/ultis/documentTypeForm";
import { formatDate } from "@/ultis/format";
import type { DocumentType } from "@/interface/DocumentType/DocumentType.interface";
import DocumentTypeForm from "./DocumentTypeForm";
import styles from "./DocumentTypes.module.scss";

export default function DocumentTypeDrawer({ id, editing, onEdit, onClose, onSaved }: {
  id: number;
  editing: boolean;
  onEdit: () => void;
  onClose: () => void;
  onSaved: (record: DocumentType) => void;
}) {
  const canManage = canManageDocumentTypes(useAuth());
  const loader = useCallback((signal: AbortSignal) => getDocumentType(id, signal), [id]);
  const { data, loading, error, reload } = useResource(loader);
  const record = data?.data.id === id ? data.data : undefined;
  if (editing && canManage && !loading && !error && record) {
    return <DocumentTypeForm record={record} onClose={onClose} onSaved={onSaved} />;
  }
  return <Drawer title={editing && canManage ? "Sửa loại văn bản" : "Chi tiết loại văn bản"} open size={560} onClose={onClose}
    footer={canManage && !loading && !error && record && <div className={styles.footer}>
      <Button type="primary" icon={<EditOutlined />} onClick={onEdit}>Sửa thông tin</Button>
    </div>}>
    {loading ? <Skeleton active paragraph={{ rows: 6 }} />
      : error ? <Alert type="error" showIcon title={error} action={<Button onClick={reload}>Thử lại</Button>} />
      : record && <Descriptions column={1} layout="vertical" items={[
        { key: "code", label: "Mã loại văn bản", children: record.code },
        { key: "name", label: "Tên loại văn bản", children: record.name },
        { key: "description", label: "Mô tả", children: <span className={styles.description}>{record.description || "Chưa có mô tả"}</span> },
        { key: "status", label: "Trạng thái", children: <Tag color={record.is_active ? "success" : "default"}>{record.is_active ? "Đang sử dụng" : "Ngừng sử dụng"}</Tag> },
        { key: "created", label: "Ngày tạo", children: formatDate(record.created_at) },
      ]} />}
  </Drawer>;
}
