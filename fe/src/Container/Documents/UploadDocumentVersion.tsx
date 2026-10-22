"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Modal, Progress, Upload } from "antd";
import type { UploadFile } from "antd";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { uploadDocumentVersion } from "@/apis/documentApis";
import type { DocumentVersion } from "@/interface/Document/Document.interface";
import { documentFileError } from "@/ultis/documentUpload";
import { requestError } from "@/ultis/requestError";
import styles from "./DocumentVersions.module.scss";

export default function UploadDocumentVersion({ documentId, disabled, onUploaded, onUploadingChange }: {
  documentId: number;
  disabled?: boolean;
  onUploaded: (version: DocumentVersion) => void;
  onUploadingChange: (uploading: boolean) => void;
}) {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => { request.current?.abort(); }, []);

  function close() {
    if (request.current) return;
    setOpen(false); setFiles([]); setError(null); setProgress(0);
  }

  async function upload() {
    const file = files[0]?.originFileObj;
    if (!file || request.current) return;
    const invalid = documentFileError(file);
    if (invalid) { setError(invalid); return; }
    const controller = new AbortController();
    request.current = controller;
    setUploading(true); setError(null); setProgress(0); onUploadingChange(true);
    try {
      const result = await uploadDocumentVersion(documentId, file, (percent) => {
        if (!controller.signal.aborted) setProgress(percent);
      }, controller.signal);
      if (controller.signal.aborted) return;
      setOpen(false); setFiles([]);
      onUploaded(result.data);
      void message.success(`Đã tải lên phiên bản ${result.data.version_number}.`);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      setError(status === 413 ? "Dung lượng file không được vượt quá 20 MB."
        : status === 422 ? "File không hợp lệ. Vui lòng chọn PDF hoặc DOCX có nội dung hợp lệ, tối đa 20 MB."
        : status === 404 ? "Văn bản không còn tồn tại. Vui lòng làm mới danh sách."
        : !status || status === 503 || status === 504 ? "Chưa xác nhận được kết quả tải lên. Hãy đóng cửa sổ này và làm mới danh sách phiên bản trước khi thử lại."
        : requestError(cause));
    } finally {
      request.current = null;
      onUploadingChange(false);
      if (!controller.signal.aborted) setUploading(false);
    }
  }

  return <>
    <Button type="primary" icon={<UploadOutlined />} onClick={() => setOpen(true)} disabled={disabled}>Tải lên phiên bản mới</Button>
    <Modal title="Tải lên phiên bản mới" open={open} onCancel={close} onOk={() => void upload()}
      okText="Tải lên" cancelText="Hủy" confirmLoading={uploading} okButtonProps={{ disabled: !files.length }}
      cancelButtonProps={{ disabled: uploading }} closable={!uploading} keyboard={!uploading} mask={{ closable: !uploading }}>
      <p className={styles.uploadNote}>File mới sẽ trở thành phiên bản đang sử dụng. Các phiên bản cũ vẫn được giữ lại.</p>
      {error && <Alert role="alert" type="error" showIcon title={error} className={styles.error} />}
      <Upload.Dragger accept=".pdf,.docx" multiple={false} maxCount={1} disabled={uploading} fileList={files}
        showUploadList={{ showPreviewIcon: false, showDownloadIcon: false, showRemoveIcon: !uploading }}
        beforeUpload={(file, selected) => {
          if (request.current) return Upload.LIST_IGNORE;
          const invalid = selected.length !== 1 ? "Mỗi lần chỉ tải lên một file." : documentFileError(file);
          if (invalid) { setError(invalid); return Upload.LIST_IGNORE; }
          setFiles([{ uid: file.uid, name: file.name, size: file.size, originFileObj: file }]);
          setError(null); setProgress(0);
          return false;
        }} onRemove={() => {
          if (request.current) return false;
          setFiles([]); setError(null); return true;
        }}>
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">Kéo thả file vào đây hoặc bấm để chọn</p>
        <p className="ant-upload-hint">PDF hoặc DOCX · Tối đa 20 MB</p>
      </Upload.Dragger>
      {uploading && <div className={styles.uploadProgress} role="status" aria-live="polite">
        <Progress percent={progress} status="active" />
        <span>{progress < 100 ? "Đang gửi file…" : "Đã gửi file. Đang lưu phiên bản…"}</span>
      </div>}
    </Modal>
  </>;
}
