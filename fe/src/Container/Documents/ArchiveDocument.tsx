"use client";
import { useRef, useState } from "react";
import { Alert, Button, Modal } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { archiveDocument } from "@/apis/documentApis";
import type { DocumentDetail } from "@/interface/Document/Document.interface";
import { requestError } from "@/ultis/requestError";

export default function ArchiveDocument({ document, disabled, onArchived, onPendingChange }: {
  document: DocumentDetail;
  disabled: boolean;
  onArchived: (document: DocumentDetail) => void;
  onPendingChange: (pending: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);

  async function archive() {
    if (pending.current || document.publication_status === "archived") return;
    pending.current = true;
    setSubmitting(true); setError(null); onPendingChange(true);
    try {
      const { data } = await archiveDocument(document.id);
      setOpen(false);
      onArchived(data);
    } catch (cause) {
      setError(isAxiosError(cause) && cause.response?.status === 401
        ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại." : requestError(cause));
    } finally {
      pending.current = false;
      setSubmitting(false); onPendingChange(false);
    }
  }

  return <>
    <Button icon={<InboxOutlined />} disabled={disabled || document.publication_status === "archived"}
      onClick={() => { setError(null); setOpen(true); }}>{document.publication_status === "archived" ? "Đã lưu trữ" : "Lưu trữ"}</Button>
    <Modal title="Lưu trữ văn bản?" open={open} okText="Lưu trữ" cancelText="Hủy" confirmLoading={submitting}
      onOk={() => void archive()} onCancel={() => { if (!pending.current) setOpen(false); }}
      cancelButtonProps={{ disabled: submitting }} closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}>
      <p>Bạn muốn lưu trữ văn bản <strong>{document.code} — {document.title}</strong>?</p>
      <p>Văn bản sẽ được ẩn khỏi danh sách chưa lưu trữ. Thông tin, file và các phiên bản vẫn được giữ lại; bạn có thể xem bằng bộ lọc Lưu trữ.</p>
      {error && <Alert role="alert" type="error" showIcon title={error} />}
    </Modal>
  </>;
}
