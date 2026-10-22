"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Empty, Pagination, Skeleton, Tag } from "antd";
import { DownloadOutlined, FilePdfOutlined, FileTextOutlined, FileWordOutlined, ReloadOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { getDocumentDownload, getDocumentVersions } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentVersion } from "@/interface/Document/Document.interface";
import { downloadFile } from "@/ultis/downloadFile";
import { requestError } from "@/ultis/requestError";
import UploadDocumentVersion from "./UploadDocumentVersion";
import styles from "./DocumentVersions.module.scss";

const pageSize = 5;
const dateTime = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const unit = bytes < 1024 * 1024 ? "KB" : "MB";
  const amount = bytes / (unit === "KB" ? 1024 : 1024 * 1024);
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(amount)} ${unit}`;
}

export default function DocumentVersions({ documentId, onUploadingChange }: {
  documentId: number;
  onUploadingChange: (uploading: boolean) => void;
}) {
  const [page, setPage] = useState(1);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const loader = useCallback((signal: AbortSignal) => getDocumentVersions(documentId, {
    page, itemsPerPage: pageSize,
  }, signal), [documentId, page]);
  const { data, loading, error, reload } = useResource(loader);

  useEffect(() => () => { request.current?.abort(); }, []);

  async function download(version: DocumentVersion) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setDownloadingId(version.id);
    setDownloadError(null);
    try {
      // Always request a fresh URL and pass the record ID, not version_number.
      const { data: file } = await getDocumentDownload(documentId, version.id, controller.signal);
      if (!controller.signal.aborted) downloadFile(file);
    } catch (cause) {
      if (controller.signal.aborted) return;
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      setDownloadError(status === 404 ? "Không tìm thấy file của phiên bản này. Vui lòng làm mới danh sách."
        : status === 409 ? "File của phiên bản này chưa hỗ trợ tải xuống từ kho lưu trữ."
        : status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : requestError(cause));
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setDownloadingId(null);
    }
  }

  return <section aria-label="Danh sách phiên bản">
    <div className={styles.toolbar}>
      <span>{data?.meta ? `${data.meta.total} phiên bản · Mới nhất trước` : "Lịch sử phiên bản"}</span>
      <div className={styles.actions}>
        <Button size="small" icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button>
        <UploadDocumentVersion documentId={documentId} disabled={downloadingId !== null} onUploadingChange={onUploadingChange}
          onUploaded={() => { setPage(1); setDownloadError(null); reload(); }} />
      </div>
    </div>
    {downloadError && <Alert role="alert" type="error" showIcon title={downloadError} className={styles.error} />}
    {loading ? <Skeleton active paragraph={{ rows: 7 }} />
      : error ? <Alert type="error" showIcon title={error} action={<Button onClick={reload}>Thử lại</Button>} />
      : data?.data.length ? <>
        <ul className={styles.list}>
          {data.data.map((version) => <li key={version.id} className={styles.version}>
            <div className={styles.header}>
              <div className={styles.title}><h3>Phiên bản {version.version_number}</h3>{version.is_current && <Tag color="green">Đang sử dụng</Tag>}</div>
              <Button icon={<DownloadOutlined />} loading={downloadingId === version.id}
                disabled={downloadingId !== null && downloadingId !== version.id}
                onClick={() => void download(version)} aria-label={`Tải xuống phiên bản ${version.version_number}: ${version.file.original_name}`}>Tải xuống</Button>
            </div>
            <div className={styles.file}>
              <span className={styles.icon} aria-hidden="true">{version.file.mime_type === "application/pdf" ? <FilePdfOutlined />
                : version.file.mime_type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ? <FileWordOutlined /> : <FileTextOutlined />}</span>
              <div className={styles.fileInfo}>
                <div className={styles.fileName}>{version.file.original_name}</div>
                <div className={styles.meta}>{fileSize(version.file.size_bytes)} · Tạo lúc {dateTime.format(new Date(version.created_at))}</div>
              </div>
            </div>
          </li>)}
        </ul>
        <div className={styles.pagination}><Pagination current={page} pageSize={pageSize} total={data.meta?.total ?? data.data.length}
          onChange={setPage} showSizeChanger={false} hideOnSinglePage size="small" disabled={downloadingId !== null} /></div>
      </> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có phiên bản">
        <p className={styles.emptyNote}>Văn bản này chưa được tải file lên.</p>
      </Empty>}
  </section>;
}
