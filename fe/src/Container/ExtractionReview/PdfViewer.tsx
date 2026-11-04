"use client";
import { useEffect, useRef, useState } from "react";
import { Alert, Button, InputNumber, Space, Spin, Tag } from "antd";
import { DownloadOutlined, LeftOutlined, MinusOutlined, PlusOutlined, RightOutlined } from "@ant-design/icons";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import { getDocumentDownload } from "@/apis/documentApis";
import { downloadFile } from "@/ultis/downloadFile";
import { requestError } from "@/ultis/requestError";
import type { Evidence } from "@/interface/Extraction/Extraction.interface";
import { evidenceParts } from "@/ultis/extractionReview";
import styles from "./ExtractionReview.module.scss";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
const options = { cMapUrl: "/pdfjs/cmaps/", standardFontDataUrl: "/pdfjs/standard_fonts/", wasmUrl: "/pdfjs/wasm/", disableRange: true, isEvalSupported: false };

export default function PdfViewer({ documentId, versionId, evidence }: { documentId: number; versionId: number; evidence?: Evidence }) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(500);
  const [pages, setPages] = useState(0);
  const [navigation, setNavigation] = useState<{ evidenceId?: number; page: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [passwordRequired, setPasswordRequired] = useState(false);
  const requestedPage = navigation && navigation.evidenceId === evidence?.id ? navigation.page : evidence?.page_number ?? 1;
  const page = Math.max(1, Math.min(requestedPage, pages || requestedPage));
  const go = (next: number) => setNavigation({ evidenceId: evidence?.id, page: Math.max(1, Math.min(next, pages || 1)) });
  const parts = evidence && evidenceParts(evidence);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(180, entry.contentRect.width - 24)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  async function download() {
    setDownloading(true); setDownloadError(null);
    try { downloadFile((await getDocumentDownload(documentId, versionId)).data); }
    catch (error) { setDownloadError(requestError(error)); }
    finally { setDownloading(false); }
  }
  const retry = () => { setPasswordRequired(false); setPages(0); setAttempt((value) => value + 1); };
  return <section className={styles.panel} aria-label="PDF và bằng chứng nguồn">
    <div className={styles.panelHeading}><h2>Văn bản gốc</h2><Button icon={<DownloadOutlined />} size="small" loading={downloading} onClick={() => void download()}>Tải PDF</Button></div>
    {downloadError && <Alert type="error" showIcon title={downloadError} />}
    <div className={styles.pdfToolbar}>
      <Space size={4}>
        <Button size="small" aria-label="Trang trước" icon={<LeftOutlined />} disabled={!pages || page <= 1} onClick={() => go(page - 1)} />
        <InputNumber aria-label="Trang PDF" size="small" min={1} max={pages || 1} value={page} disabled={!pages} controls={false} onChange={(value) => { if (value !== null) go(value); }} style={{ width: 55 }} />
        <span>/ {pages || "—"}</span>
        <Button size="small" aria-label="Trang sau" icon={<RightOutlined />} disabled={!pages || page >= pages} onClick={() => go(page + 1)} />
      </Space>
      <Space size={4}>
        <Button size="small" aria-label="Thu nhỏ PDF" icon={<MinusOutlined />} disabled={zoom <= 0.75} onClick={() => setZoom((value) => Math.max(.75, value - .25))} />
        <span>{Math.round(zoom * 100)}%</span>
        <Button size="small" aria-label="Phóng to PDF" icon={<PlusOutlined />} disabled={zoom >= 2} onClick={() => setZoom((value) => Math.min(2, value + .25))} />
      </Space>
    </div>
    {pages > 0 && requestedPage > pages && <Alert type="warning" title="Trang ghi trong bằng chứng vượt quá số trang PDF. Vui lòng kiểm tra văn bản nguồn." />}
    {passwordRequired && <Alert type="warning" title="PDF có mật khẩu. Hãy tải file để mở bằng trình đọc PDF." />}
    <div className={styles.pdfViewport} ref={container}>
      <Document key={attempt} file={`/api/documents/${documentId}/versions/${versionId}/pdf?attempt=${attempt}`} options={options} suspense={false}
        onLoadSuccess={({ numPages }) => setPages(numPages)} onPassword={() => setPasswordRequired(true)}
        loading={<div className={styles.pdfLoading}><Spin /><span>Đang tải PDF…</span></div>}
        error={<Alert type="error" showIcon title="Không thể mở PDF" description="File có thể chưa sẵn sàng hoặc phiên truy cập đã hết hạn." action={<Button onClick={retry}>Thử lại</Button>} />}>
        <Page pageNumber={page} width={width * zoom} suspense={false} renderAnnotationLayer={false}
          loading={<div className={styles.pdfLoading}><Spin /></div>}
          error={<Alert type="error" title="Không thể hiển thị trang này" action={<Button onClick={retry}>Tải lại</Button>} />} />
      </Document>
    </div>
    <div className={styles.source}>
      <div className={styles.sourceHeading}><h3>Đoạn nguồn được đánh dấu</h3>{evidence?.page_number && <Tag>Trang {evidence.page_number}</Tag>}</div>
      {evidence ? <>
        <p className={styles.sourceMeta}>{evidence.section_title || "Đoạn văn bản"} · Segment #{evidence.source_segment_id}</p>
        {evidence.document_segment_id === null && <Alert type="info" showIcon title="Bằng chứng được lưu từ lần trích xuất trước khi văn bản được xử lý lại." />}
        <blockquote>{parts ? <>{parts.before}<mark>{parts.quote}</mark>{parts.after}</> : evidence.segment_content_snapshot}</blockquote>
        {!parts && <Alert type="warning" title="Không xác định được vị trí đánh dấu trong đoạn nguồn." />}
        <p className={styles.hint}>Đánh dấu trên nội dung trích xuất. Chọn bằng chứng để chuyển đến trang PDF tương ứng.</p>
      </> : <p className={styles.hint}>Chọn một kết quả để xem đoạn nguồn tương ứng.</p>}
    </div>
  </section>;
}
