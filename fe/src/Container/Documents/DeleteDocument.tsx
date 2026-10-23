"use client";
import { useRef, useState } from "react";
import { Alert, Modal } from "antd";
import { isAxiosError } from "axios";
import { deleteDocument } from "@/apis/documentApis";
import type { DocumentItem } from "@/interface/Document/Document.interface";
import { requestError } from "@/ultis/requestError";

export default function DeleteDocument({ document, onClose, onDeleted }: {
  document: DocumentItem;
  onClose: () => void;
  onDeleted: (alreadyDeleted?: boolean) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);

  async function remove() {
    if (pending.current) return;
    pending.current = true; setSubmitting(true); setError(null);
    try {
      await deleteDocument(document.id);
      onDeleted();
    } catch (cause) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      if (status === 404) { onDeleted(true); return; }
      setError(status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : status === 403 ? "Bạn không có quyền xóa văn bản này."
        : requestError(cause));
    } finally {
      pending.current = false; setSubmitting(false);
    }
  }

  return <Modal title="Xóa văn bản?" open okText="Xóa văn bản" cancelText="Hủy" okButtonProps={{ danger: true }}
    confirmLoading={submitting} onOk={() => void remove()} onCancel={() => { if (!pending.current) onClose(); }}
    closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }} cancelButtonProps={{ disabled: submitting }}>
    <p>Bạn muốn xóa <strong>{document.code} — {document.title}</strong>?</p>
    <p>Văn bản sẽ không còn xuất hiện trong danh sách, kể cả mục Lưu trữ. Bạn sẽ không thể xem hoặc tải file của văn bản này qua hệ thống.</p>
    <p>Dữ liệu và file gốc được giữ lại trong kho lưu trữ.</p>
    {error && <Alert role="alert" type="error" showIcon title={error} />}
  </Modal>;
}
