"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Alert, App, Button, Collapse, Empty, Pagination, Select, Skeleton, Space, Tag } from "antd";
import { ArrowLeftOutlined, CheckOutlined, CloseOutlined, EditOutlined, ReloadOutlined, ScanOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { getDocument, getDocumentVersions } from "@/apis/documentApis";
import { createExtractionRun, getExtractedFields, getExtractionRun, getExtractionRuns, retryExtractionRun } from "@/apis/extractionApis";
import type { DocumentVersion } from "@/interface/Document/Document.interface";
import type { ExtractedField, ExtractionRun, FieldKey, FieldReview, ReviewStatus } from "@/interface/Extraction/Extraction.interface";
import useResource from "@/hooks/useResource";
import { fieldDisplayValue, fieldLabels, reviewLabels, runLabels } from "@/ultis/extractionReview";
import { requestError } from "@/ultis/requestError";
import ReviewDialog from "./ReviewDialog";
import ReviewHistory from "./ReviewHistory";
import styles from "./ExtractionReview.module.scss";

const PdfViewer = dynamic(() => import("./PdfViewer"), { ssr: false, loading: () => <div className={styles.panel}><Skeleton active paragraph={{ rows: 12 }} /></div> });
const colors = { pending: "gold", processing: "blue", completed: "green", failed: "red", approved: "green", rejected: "red" };
const timestamp = (value: string) => new Date(value).toLocaleString("vi-VN");

async function findVersion(documentId: number, versionId: number, signal: AbortSignal) {
  for (let page = 1; ; page += 1) {
    const response = await getDocumentVersions(documentId, { page, itemsPerPage: 100 }, signal);
    const version = response.data.find((item) => item.id === versionId);
    if (version) return version;
    if (!response.meta || page >= response.meta.totalPages || !response.data.length) throw new Error("Không tìm thấy phiên bản văn bản này.");
  }
}

export default function DocumentExtractionReview({ documentId, versionId }: { documentId: number; versionId: number }) {
  const loader = useCallback(async (signal: AbortSignal) => {
    const [document, version] = await Promise.all([getDocument(documentId, signal), findVersion(documentId, versionId, signal)]);
    return { document: document.data, version };
  }, [documentId, versionId]);
  const { data, loading, error, reload } = useResource(loader);
  useEffect(() => {
    if (data && ["pending", "processing"].includes(data.version.parse_status) && !error) {
      const timer = setTimeout(reload, 5000);
      return () => clearTimeout(timer);
    }
  }, [data, error, reload]);
  return <div className={styles.review}>
    <Link href={`/documents?id=${documentId}`} className={styles.back}><ArrowLeftOutlined /> Quay lại văn bản</Link>
    <div className={styles.heading}><div><span className={styles.eyebrow}>DOCUMENT EXTRACTION REVIEW</span><h1>Đối chiếu kết quả trích xuất</h1>
      <p>{data ? `${data.document.title} · Phiên bản ${data.version.version_number}` : "Đang tải thông tin văn bản…"}</p></div>
      <Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button>
    </div>
    {error ? <Alert type="error" showIcon title={error} action={<Button onClick={reload}>Thử lại</Button>} />
      : !data ? <Skeleton active paragraph={{ rows: 12 }} />
      : data.version.file.mime_type !== "application/pdf" ? <Empty description="Màn hình đối chiếu hiện hỗ trợ phiên bản PDF." />
      : <Workspace documentId={documentId} version={data.version} />}
  </div>;
}

function Workspace({ documentId, version }: { documentId: number; version: DocumentVersion }) {
  const [historyPage, setHistoryPage] = useState(1);
  const [selectedRun, setSelectedRun] = useState<number | null>(null);
  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const createKey = useRef<string | null>(null);
  const loader = useCallback((signal: AbortSignal) => getExtractionRuns(version.id, historyPage, signal), [version.id, historyPage]);
  const { data, loading, error, reload } = useResource(loader);
  useEffect(() => { reload(); }, [version.parse_status, reload]);
  const runId = selectedRun ?? data?.data[0]?.id;
  const [refresh, setRefresh] = useState(0);
  const refreshAll = () => { reload(); setRefresh((value) => value + 1); };
  async function queue(id?: number) {
    if (working) return;
    setWorking(true); setActionError(null);
    try {
      createKey.current ??= crypto.randomUUID();
      const result = id ? await retryExtractionRun(id) : await createExtractionRun(version.id, createKey.current);
      createKey.current = null;
      setSelectedRun(result.data.id); setHistoryPage(1); refreshAll();
    } catch (cause) {
      const saved = isAxiosError(cause) ? cause.response?.data?.data as ExtractionRun | undefined : undefined;
      if (saved?.id && saved.document_version_id === version.id) {
        setSelectedRun(saved.id); createKey.current = null; refreshAll();
        setActionError("Lần trích xuất đã được lưu nhưng chưa đưa vào hàng đợi. Bấm “Thử lại” khi dịch vụ xử lý hoạt động.");
      } else setActionError(requestError(cause));
    } finally { setWorking(false); }
  }
  return <>
    {version.parse_status !== "parsed" && <Alert showIcon type={version.parse_status === "failed" ? "error" : "info"}
      title={version.parse_status === "failed" ? "Xử lý văn bản thất bại" : "Đang chờ xử lý nội dung văn bản"}
      description={version.parse_status === "failed" ? "Cần xử lý lại phiên bản trước khi tạo lần trích xuất mới." : "Kết quả sẽ xuất hiện sau khi tác vụ nền xử lý xong."} />}
    <div className={styles.runToolbar}>
      <div><span className={styles.label}>Lần trích xuất</span><Select aria-label="Chọn lần trích xuất" className={styles.runSelect} value={runId} loading={loading} placeholder="Chưa có lần trích xuất"
        onChange={setSelectedRun} options={(data?.data ?? []).map((run) => ({ value: run.id, label: `#${run.id} · ${timestamp(run.created_at)} · ${runLabels[run.status]}` }))} />
        <Pagination size="small" current={historyPage} pageSize={20} total={data?.meta?.total ?? 0} onChange={(page) => { setSelectedRun(null); setHistoryPage(page); }} hideOnSinglePage showSizeChanger={false} />
      </div>
      <Space wrap><Button icon={<ReloadOutlined />} onClick={refreshAll} disabled={working}>Cập nhật kết quả</Button>
        <Button type="primary" icon={<ScanOutlined />} loading={working} disabled={version.parse_status !== "parsed" || !!error} onClick={() => void queue()}>{data?.data.length ? "Trích xuất lại" : "Trích xuất ngay"}</Button></Space>
    </div>
    {(error || actionError) && <Alert type="error" showIcon title={error || actionError} action={error && <Button onClick={reload}>Thử lại</Button>} />}
    {runId ? <RunComparison key={runId} runId={runId} documentId={documentId} versionId={version.id} refresh={refresh} onRetry={() => void queue(runId)} retrying={working} />
      : <div className={styles.columns}><PdfViewer documentId={documentId} versionId={version.id} /><section className={styles.panel}><h2>Kết quả trích xuất</h2>
        {loading ? <Skeleton active /> : <Empty description={error ? "Chưa tải được kết quả" : "Chưa có kết quả trích xuất"} />}</section></div>}
  </>;
}

function RunComparison({ runId, documentId, versionId, refresh, onRetry, retrying }: {
  runId: number; documentId: number; versionId: number; refresh: number; onRetry: () => void; retrying: boolean;
}) {
  const { message } = App.useApp();
  const runLoader = useCallback(async (signal: AbortSignal) => {
    const result = await getExtractionRun(runId, signal);
    return { ...result, leaseExpired: !!result.data.lease_expires_at && new Date(result.data.lease_expires_at).getTime() < Date.now() };
  }, [runId]);
  const run = useResource(runLoader);
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState<FieldKey | undefined>();
  const [status, setStatus] = useState<ReviewStatus | undefined>();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [evidenceId, setEvidenceId] = useState<number | null>(null);
  const [review, setReview] = useState<{ field: ExtractedField; action: FieldReview["action"] } | null>(null);
  const fieldsLoader = useCallback((signal: AbortSignal) => getExtractedFields(runId, { page, itemsPerPage: 10, field_key: kind, review_status: status }, signal), [runId, page, kind, status]);
  const fields = useResource(fieldsLoader);
  const { reload: reloadRun } = run;
  const { reload: reloadFields } = fields;
  useEffect(() => { reloadRun(); reloadFields(); }, [refresh, reloadRun, reloadFields]);
  useEffect(() => {
    if (run.data?.data.status === "completed") reloadFields();
  }, [run.data?.data.status, reloadFields]);
  useEffect(() => {
    if (run.data && ["pending", "processing"].includes(run.data.data.status) && !run.error) {
      const timer = setTimeout(reloadRun, 4000);
      return () => clearTimeout(timer);
    }
  }, [run.data, run.error, reloadRun]);
  const items = fields.error ? [] : fields.data?.data ?? [];
  const selected = items.find((item) => item.id === selectedId) ?? items[0];
  const evidences = selected ? [...selected.evidences].sort((a, b) => Number(a.role === "context") - Number(b.role === "context") || a.occurrence_index - b.occurrence_index || a.id - b.id) : [];
  const evidence = evidences.find((item) => item.id === evidenceId) ?? evidences[0];
  const current = run.data?.data;
  const busy = review !== null;
  return <>
    {run.error && <Alert type="error" showIcon title={run.error} action={<Button onClick={reloadRun}>Thử lại</Button>} />}
    {current && <div className={styles.runSummary}>
      <Space wrap><Tag color={colors[current.status]}>{runLabels[current.status]}</Tag><span>{current.field_count} kết quả · {current.rule_version}</span></Space>
      {(current.status === "failed" || current.status === "pending" || (current.status === "processing" && run.data?.leaseExpired)) && <Button size="small" loading={retrying} onClick={onRetry}>Thử lại</Button>}
    </div>}
    {current?.error_message && <Alert type={current.status === "failed" ? "error" : "warning"} showIcon title="Cần kiểm tra lần trích xuất" description={current.error_code === "source_changed" || current.error_code === "rule_version_changed" ? "Nguồn hoặc quy tắc đã thay đổi. Hãy tạo lần trích xuất mới." : current.error_message} />}
    {!!current?.warnings.length && <Alert type="warning" showIcon title="Lưu ý khi đối chiếu" description={current.warnings.join(" · ")} />}
    <div className={styles.columns}>
      <PdfViewer documentId={documentId} versionId={versionId} evidence={evidence} />
      <section className={styles.panel} aria-label="Kết quả trích xuất">
        <div className={styles.panelHeading}><h2>Kết quả trích xuất</h2><Tag>{fields.data?.meta?.total ?? 0} kết quả</Tag></div>
        <div className={styles.filters}>
          <Select aria-label="Lọc loại thông tin" value={kind} allowClear placeholder="Tất cả loại thông tin" disabled={busy} onChange={(value) => { setKind(value); setPage(1); setSelectedId(null); }} options={Object.entries(fieldLabels).map(([value, label]) => ({ value, label }))} />
          <Select aria-label="Lọc trạng thái duyệt" value={status} allowClear placeholder="Tất cả trạng thái" disabled={busy} onChange={(value) => { setStatus(value); setPage(1); setSelectedId(null); }} options={Object.entries(reviewLabels).map(([value, label]) => ({ value, label }))} />
        </div>
        {fields.loading ? <Skeleton active paragraph={{ rows: 6 }} /> : fields.error ? <Alert type="error" title={fields.error} action={<Button onClick={reloadFields}>Thử lại</Button>} />
          : !items.length ? <Empty description={current?.status === "completed" ? "Không có kết quả phù hợp" : "Kết quả sẽ hiển thị khi trích xuất hoàn tất"} />
          : <>
            <div className={styles.fieldList} role="group" aria-label="Chọn kết quả đối chiếu">
              {items.map((field) => <button key={field.id} className={`${styles.fieldChoice} ${selected?.id === field.id ? styles.selected : ""}`} aria-pressed={selected?.id === field.id} disabled={busy}
                onClick={() => { setSelectedId(field.id); setEvidenceId(null); }}><span>{fieldLabels[field.field_key]} <Tag color={colors[field.review_status]}>{reviewLabels[field.review_status]}</Tag></span><b>{fieldDisplayValue(field)}</b></button>)}
            </div>
            {selected && <article className={styles.fieldDetail}>
              <span className={styles.label}>{fieldLabels[selected.field_key]}</span><p className={styles.fieldValue}>{fieldDisplayValue(selected)}</p>
              <Tag color={colors[selected.review_status]}>{reviewLabels[selected.review_status]}</Tag>
              <Collapse ghost size="small" items={[{ key: "original", label: "Giá trị trích xuất gốc", children: <p className={styles.original}>{selected.raw_value}</p> }]} />
              <div className={styles.evidenceList}><span className={styles.label}>Bằng chứng · {evidences.length} đoạn</span>
                {evidences.length ? evidences.map((item, index) => <button key={item.id} className={item.id === evidence?.id ? styles.evidenceSelected : ""} disabled={busy} onClick={() => setEvidenceId(item.id)} aria-pressed={item.id === evidence?.id}>
                  <b>{item.page_number ? `Trang ${item.page_number}` : "Chưa rõ trang"} · Segment #{item.source_segment_id}</b><span>{item.role === "context" ? "Ngữ cảnh" : "Đoạn trích"} {index + 1} · {item.section_title || "Văn bản"}</span>
                </button>) : <p>Không có bằng chứng nguồn.</p>}
              </div>
              <div className={styles.reviewActions}>
                <Button className={styles.approve} type="primary" icon={<CheckOutlined />} disabled={busy || !!run.error || current?.status !== "completed" || selected.review_status === "approved"} onClick={() => setReview({ field: selected, action: "approve" })}>Duyệt</Button>
                <Button icon={<EditOutlined />} disabled={busy || !!run.error || current?.status !== "completed"} onClick={() => setReview({ field: selected, action: "correct" })}>Chỉnh sửa</Button>
                <Button danger className={styles.reject} icon={<CloseOutlined />} disabled={busy || !!run.error || current?.status !== "completed" || selected.review_status === "rejected"} onClick={() => setReview({ field: selected, action: "reject" })}>Từ chối</Button>
              </div>
              <Collapse ghost items={[{ key: "history", label: "Lịch sử duyệt", children: <ReviewHistory key={`${selected.id}:${selected.review_revision}`} fieldId={selected.id} /> }]} />
            </article>}
            <Pagination current={page} pageSize={10} total={fields.data?.meta?.total ?? 0} size="small" disabled={busy} onChange={(next) => { setPage(next); setSelectedId(null); }} hideOnSinglePage showSizeChanger={false} />
          </>}
      </section>
    </div>
    {review && <ReviewDialog field={review.field} action={review.action} onClose={() => setReview(null)} onConflict={reloadFields} onSaved={() => { setReview(null); reloadFields(); void message.success("Đã lưu kết quả duyệt."); }} />}
  </>;
}
