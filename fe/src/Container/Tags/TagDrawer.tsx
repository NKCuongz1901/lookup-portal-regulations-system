"use client";
import { useCallback } from "react";
import { Alert, Button, Descriptions, Drawer, Skeleton } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { getTag } from "@/apis/tagApis";
import useResource from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import { canManageTags } from "@/ultis/tagForm";
import { formatDate } from "@/ultis/format";
import type { TagItem } from "@/interface/Tag/Tag.interface";
import TagForm from "./TagForm";
import styles from "./Tags.module.scss";

export default function TagDrawer({ id, editing, onEdit, onClose, onSaved }: {
  id: number;
  editing: boolean;
  onEdit: () => void;
  onClose: () => void;
  onSaved: (record: TagItem) => void;
}) {
  const canManage = canManageTags(useAuth());
  const loader = useCallback((signal: AbortSignal) => getTag(id, signal), [id]);
  const { data, loading, error, reload } = useResource(loader);
  const record = data?.data.id === id ? data.data : undefined;
  if (editing && canManage && !loading && !error && record) {
    return <TagForm record={record} onClose={onClose} onSaved={onSaved} />;
  }
  return <Drawer title={editing && canManage ? "Sửa thẻ" : "Chi tiết thẻ"} open size={560} onClose={onClose}
    footer={canManage && !loading && !error && record && <div className={styles.footer}>
      <Button type="primary" icon={<EditOutlined />} onClick={onEdit}>Sửa thông tin</Button>
    </div>}>
    {loading ? <Skeleton active paragraph={{ rows: 4 }} />
      : error ? <Alert type="error" showIcon title={error} action={<Button onClick={reload}>Thử lại</Button>} />
      : record && <Descriptions column={1} layout="vertical" items={[
        { key: "name", label: "Tên thẻ", children: <span className={styles.text}>{record.name}</span> },
        { key: "slug", label: "Slug", children: <span className={styles.text}>{record.slug}</span> },
        { key: "created", label: "Ngày tạo", children: formatDate(record.created_at) },
      ]} />}
  </Drawer>;
}
