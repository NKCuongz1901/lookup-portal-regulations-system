"use client";
import { useCallback, useState } from "react";
import { Alert, Button, Empty, Input, Select, Table } from "antd";
import { EyeOutlined, FileTextOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useRouter, useSearchParams } from "next/navigation";
import { getDocuments } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentItem, PublicationStatus } from "@/interface/Document/Document.interface";
import StatusTag, { publicationLabels } from "@/Components/StatusTag/StatusTag";
import { formatDate } from "@/ultis/format";
import DocumentDetail from "./DocumentDetail";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function Documents() {
  const params = useSearchParams();
  const router = useRouter();
  const statusParam = params.get("status");
  const status = statusParam && Object.hasOwn(publicationLabels, statusParam) ? statusParam as PublicationStatus : undefined;
  const idParam = Number(params.get("id"));
  const selectedId = Number.isSafeInteger(idParam) && idParam > 0 ? idParam : null;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const loader = useCallback((signal: AbortSignal) => getDocuments({ page, itemsPerPage: pageSize, search: search || undefined, publication_status: status }, signal), [page, pageSize, search, status]);
  const { data, loading, error, reload } = useResource(loader);
  function updateQuery(name: string, value?: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(name, value); else next.delete(name);
    router.replace(`/documents${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  return <>
    <section className={styles.panel}>
      <div className={styles.heading}><div className={styles.headingText}><span className={styles.headingIcon}><FileTextOutlined /></span><div><h2>Danh sách văn bản <span>{data?.meta?.total ?? "—"}</span></h2><p>Tra cứu và theo dõi thông tin văn bản</p></div></div><Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button></div>
      <div className={styles.toolbar}>
        <Input.Search aria-label="Tìm văn bản" placeholder="Tìm theo mã hoặc tên văn bản…" allowClear prefix={<SearchOutlined />} onSearch={(value) => { setSearch(value.trim()); setPage(1); }} className={styles.search} />
        <Select aria-label="Lọc trạng thái văn bản" value={status || "active"} className={styles.statusFilter} onChange={(value) => { setPage(1); updateQuery("status", value === "active" ? undefined : value); }} options={[{ value: "active", label: "Chưa lưu trữ" }, ...Object.entries(publicationLabels).map(([value, label]) => ({ value, label }))]} />
      </div>
      {error && <Alert type="error" showIcon title={error} className={styles.error} action={<Button onClick={reload}>Thử lại</Button>} />}
      <Table<DocumentItem> dataSource={data?.data || []} loading={loading} rowKey="id" scroll={{ x: 850 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={search || status ? "Không tìm thấy văn bản phù hợp" : "Chưa có văn bản nào"} /> }}
        pagination={{ current: page, pageSize, total: data?.meta?.total || 0, showSizeChanger: true, pageSizeOptions: [10, 20, 50], showTotal: (total) => `${total} văn bản`, onChange: (next, size) => { setPage(size === pageSize ? next : 1); setPageSize(size); } }}
        columns={[
          { title: "VĂN BẢN", key: "title", render: (_, doc) => <button className={styles.documentName} onClick={() => updateQuery("id", String(doc.id))}><span><FileTextOutlined /></span><div><b>{doc.title}</b><small>{doc.code}</small></div></button> },
          { title: "LOẠI VĂN BẢN", key: "type", width: 150, render: (_, doc) => <span className={styles.secondary}>{doc.document_type?.name || "Chưa phân loại"}</span> },
          { title: "NGÀY BAN HÀNH", dataIndex: "issue_date", width: 145, render: (value) => <span className={styles.secondary}>{value ? formatDate(value) : "—"}</span> },
          { title: "TRẠNG THÁI", dataIndex: "publication_status", width: 130, render: (value) => <StatusTag status={value} /> },
          { title: "", key: "action", width: 50, render: (_, doc) => <Button type="text" icon={<EyeOutlined />} aria-label={`Xem ${doc.code}`} onClick={() => updateQuery("id", String(doc.id))} /> },
        ]} />
    </section>
    {selectedId && <DocumentDetail id={selectedId} onClose={() => updateQuery("id")} />}
  </>;
}
