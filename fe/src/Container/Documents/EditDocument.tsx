"use client";
import { useCallback } from "react";
import { Alert, Button, Drawer, Skeleton } from "antd";
import { getDocument } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentDetail } from "@/interface/Document/Document.interface";
import DocumentForm from "./DocumentForm";

export default function EditDocument({ id, onClose, onSaved }: {
  id: number;
  onClose: () => void;
  onSaved: (document: DocumentDetail) => void;
}) {
  const loader = useCallback((signal: AbortSignal) => getDocument(id, signal), [id]);
  const { data, loading, error, reload } = useResource(loader);
  // The table response omits description and subjects, so load the full record.
  if (!loading && !error && data?.data.id === id) {
    return <DocumentForm document={data.data} onClose={onClose} onSaved={onSaved} />;
  }
  return <Drawer title="Sửa thông tin văn bản" open size={680} onClose={onClose} focusable={{ trap: false }}>
    {loading ? <Skeleton active paragraph={{ rows: 10 }} />
      : <Alert type="error" showIcon title={error || "Không tìm thấy văn bản."}
        action={<Button onClick={reload}>Thử lại</Button>} />}
  </Drawer>;
}
