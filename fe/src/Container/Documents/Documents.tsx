"use client";
import { useCallback, useState } from "react";
import { Alert, App, Button, Empty, Input, Select, Space, Table, Tooltip } from "antd";
import { DeleteOutlined, EditOutlined, EyeOutlined, FileTextOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useRouter, useSearchParams } from "next/navigation";
import { getDocuments } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentItem, PublicationStatus } from "@/interface/Document/Document.interface";
import StatusTag, { publicationLabels } from "@/Components/StatusTag/StatusTag";
import { formatDate } from "@/ultis/format";
import DocumentDetail from "./DocumentDetail";
import CreateDocument from "./CreateDocument";
import EditDocument from "./EditDocument";
import DeleteDocument from "./DeleteDocument";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function Documents() {
  const { message } = App.useApp();
  const params = useSearchParams();
  const router = useRouter();
  const statusParam = params.get("status");
  const status = statusParam && Object.hasOwn(publicationLabels, statusParam) ? statusParam as PublicationStatus : undefined;
  const idParam = Number(params.get("id"));
  const selectedId = Number.isSafeInteger(idParam) && idParam > 0 ? idParam : null;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentItem | null>(null);
  const loader = useCallback((signal: AbortSignal) => getDocuments({ page, itemsPerPage: pageSize, search: search || undefined, publication_status: status }, signal), [page, pageSize, search, status]);
  const { data, loading, error, reload } = useResource(loader);
  function updateQuery(name: string, value?: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(name, value); else next.delete(name);
    router.replace(`/documents${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  return <>
    <section className={styles.panel}>
      <div className={styles.heading}><div className={styles.headingText}><span className={styles.headingIcon}><FileTextOutlined /></span><div><h2>Danh sách văn bản <span>{data?.meta?.total ?? "—"}</span></h2><p>Tra cứu và theo dõi thông tin văn bản</p></div></div><div className={styles.headingActions}><Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button><Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>Tạo văn bản</Button></div></div>
      <div className={styles.toolbar}>
        <Input.Search aria-label="Tìm văn bản" placeholder="Tìm theo mã hoặc tên văn bản…" allowClear prefix={<SearchOutlined />} value={searchInput} onChange={(event) => setSearchInput(event.target.value)} onSearch={(value) => { setSearch(value.trim()); setPage(1); }} className={styles.search} />
        <Select aria-label="Lọc trạng thái văn bản" value={status || "active"} className={styles.statusFilter} onChange={(value) => { setPage(1); updateQuery("status", value === "active" ? undefined : value); }} options={[{ value: "active", label: "Chưa lưu trữ" }, ...Object.entries(publicationLabels).map(([value, label]) => ({ value, label }))]} />
      </div>
      {error && <Alert type="error" showIcon title={error} className={styles.error} action={<Button onClick={reload}>Thử lại</Button>} />}
      <Table<DocumentItem> dataSource={data?.data || []} loading={loading} rowKey="id" scroll={{ x: 950 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={search || status ? "Không tìm thấy văn bản phù hợp" : "Chưa có văn bản nào"} /> }}
        pagination={{ current: page, pageSize, total: data?.meta?.total || 0, showSizeChanger: true, pageSizeOptions: [10, 20, 50], showTotal: (total) => `${total} văn bản`, onChange: (next, size) => { setPage(size === pageSize ? next : 1); setPageSize(size); } }}
        columns={[
          { title: "VĂN BẢN", key: "title", render: (_, doc) => <button className={styles.documentName} onClick={() => updateQuery("id", String(doc.id))}><span><FileTextOutlined /></span><div><b>{doc.title}</b><small>{doc.code}</small></div></button> },
          { title: "LOẠI VĂN BẢN", key: "type", width: 150, render: (_, doc) => <span className={styles.secondary}>{doc.document_type?.name || "Chưa phân loại"}</span> },
          { title: "NGÀY BAN HÀNH", dataIndex: "issue_date", width: 145, render: (value) => <span className={styles.secondary}>{value ? formatDate(value) : "—"}</span> },
          { title: "TRẠNG THÁI", dataIndex: "publication_status", width: 130, render: (value) => <StatusTag status={value} /> },
          { title: "THAO TÁC", key: "action", width: 180, fixed: "right", render: (_, doc) => <Space size={4}>
            <Button type="text" icon={<EyeOutlined />} aria-label={`Xem ${doc.code}`} onClick={() => updateQuery("id", String(doc.id))} />
            <Button type="text" icon={<EditOutlined />} aria-label={`Sửa ${doc.code}`} onClick={() => setEditingId(doc.id)}>Sửa</Button>
            <Tooltip title="Xóa văn bản"><Button type="text" danger icon={<DeleteOutlined />} aria-label={`Xóa ${doc.code}`} onClick={() => setDeleteTarget(doc)} /></Tooltip>
          </Space> },
        ]} />
    </section>
    {selectedId && <DocumentDetail key={selectedId} id={selectedId} onClose={() => updateQuery("id")} onChanged={() => { setPage(1); reload(); }} />}
    {editingId !== null && <EditDocument key={editingId} id={editingId} onClose={() => setEditingId(null)} onSaved={(document) => {
      setEditingId(null); setPage(1); reload();
      void message.success(`Đã cập nhật văn bản ${document.code}.`);
    }} />}
    {deleteTarget && <DeleteDocument key={deleteTarget.id} document={deleteTarget} onClose={() => setDeleteTarget(null)} onDeleted={(alreadyDeleted) => {
      if (selectedId === deleteTarget.id) updateQuery("id");
      if (editingId === deleteTarget.id) setEditingId(null);
      setDeleteTarget(null); setPage(1); reload();
      if (alreadyDeleted) void message.info("Văn bản không còn tồn tại. Danh sách đã được cập nhật.");
      else void message.success(`Đã xóa văn bản ${deleteTarget.code}.`);
    }} />}
    {createOpen && <CreateDocument onClose={() => setCreateOpen(false)} onCreated={(document) => {
      setCreateOpen(false);
      setPage(1); setSearch(""); setSearchInput("");
      router.replace("/documents", { scroll: false });
      reload();
      void message.success(`Đã tạo văn bản ${document.code}.`);
    }} />}
  </>;
}
