"use client";
import { useCallback, useState } from "react";
import { Alert, App, Button, Empty, Input, Select, Space, Table, Tag } from "antd";
import { EditOutlined, EyeOutlined, BankOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { listIssuingUnits } from "@/apis/issuingUnitApis";
import { useAuth } from "@/context/AuthContext";
import useResource from "@/hooks/useResource";
import type { IssuingUnit } from "@/interface/IssuingUnit/IssuingUnit.interface";
import { canManageIssuingUnits } from "@/ultis/issuingUnitForm";
import { formatDate } from "@/ultis/format";
import IssuingUnitDrawer from "./IssuingUnitDrawer";
import IssuingUnitForm from "./IssuingUnitForm";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function IssuingUnits() {
  const { message } = App.useApp();
  const canManage = canManageIssuingUnits(useAuth());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "inactive">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<{ id: number; editing: boolean } | null>(null);
  const loader = useCallback((signal: AbortSignal) => listIssuingUnits({
    page, itemsPerPage: pageSize, search: search || undefined,
    is_active: status === "all" ? undefined : status === "active",
  }, signal), [page, pageSize, search, status]);
  const { data, loading, error, reload } = useResource(loader);

  return <>
    <section className={styles.panel}>
      <div className={styles.heading}>
        <div className={styles.headingText}><span className={styles.headingIcon}><BankOutlined /></span><div>
          <h2>Danh sách đơn vị ban hành <span>{data?.meta?.total ?? "—"}</span></h2><p>Quản lý các đơn vị chịu trách nhiệm ban hành văn bản</p>
        </div></div>
        <div className={styles.headingActions}>
          <Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button>
          {canManage && <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>Thêm đơn vị ban hành</Button>}
        </div>
      </div>
      <div className={styles.toolbar}>
        <Input.Search aria-label="Tìm đơn vị ban hành" placeholder="Tìm theo mã hoặc tên đơn vị ban hành…" maxLength={200} allowClear
          prefix={<SearchOutlined />} value={searchInput} onChange={(event) => setSearchInput(event.target.value)}
          onSearch={(value) => { setSearch(value.trim()); setPage(1); }} className={styles.search} />
        <Select aria-label="Lọc trạng thái đơn vị ban hành" value={status} className={styles.statusFilter}
          onChange={(value) => { setStatus(value); setPage(1); }} options={[
            { value: "all", label: "Tất cả trạng thái" }, { value: "active", label: "Đang sử dụng" }, { value: "inactive", label: "Ngừng sử dụng" },
          ]} />
      </div>
      {error && <Alert type="error" showIcon title={error} className={styles.error} action={<Button onClick={reload}>Thử lại</Button>} />}
      <Table<IssuingUnit> dataSource={data?.data ?? []} loading={loading} rowKey="id" scroll={{ x: 850 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={search || status !== "all" ? "Không tìm thấy đơn vị ban hành phù hợp" : "Chưa có đơn vị ban hành"} /> }}
        pagination={{ current: page, pageSize, total: data?.meta?.total ?? 0, showSizeChanger: true, pageSizeOptions: [10, 20, 50],
          showTotal: (total) => `${total} đơn vị ban hành`, onChange: (next, size) => { setPage(size === pageSize ? next : 1); setPageSize(size); } }}
        columns={[
          { title: "ĐƠN VỊ BAN HÀNH", key: "name", render: (_, record) => <button className={styles.documentName} onClick={() => setSelected({ id: record.id, editing: false })}>
            <span><BankOutlined /></span><div><b>{record.name}</b><small>{record.code}</small></div>
          </button> },
          { title: "MÔ TẢ", dataIndex: "description", ellipsis: true, width: 240, render: (value: string | null) => <span className={styles.secondary}>{value || "Chưa có mô tả"}</span> },
          { title: "TRẠNG THÁI", dataIndex: "is_active", width: 150, render: (active: boolean) => <Tag color={active ? "success" : "default"}>{active ? "Đang sử dụng" : "Ngừng sử dụng"}</Tag> },
          { title: "NGÀY TẠO", dataIndex: "created_at", width: 130, render: (value: string) => <span className={styles.secondary}>{formatDate(value)}</span> },
          { title: "THAO TÁC", key: "actions", width: canManage ? 140 : 100, fixed: "right", render: (_, record) => <Space size={4}>
            <Button type="text" icon={<EyeOutlined />} aria-label={`Xem đơn vị ban hành ${record.code}`} onClick={() => setSelected({ id: record.id, editing: false })} />
            {canManage && <Button type="text" icon={<EditOutlined />} aria-label={`Sửa đơn vị ban hành ${record.code}`} onClick={() => setSelected({ id: record.id, editing: true })}>Sửa</Button>}
          </Space> },
        ]} />
    </section>
    {selected && <IssuingUnitDrawer key={selected.id} id={selected.id} editing={selected.editing} onClose={() => setSelected(null)}
      onEdit={() => { if (canManage) setSelected({ ...selected, editing: true }); }} onSaved={(record) => {
        setSelected(null); setPage(1); reload(); void message.success(`Đã cập nhật đơn vị ban hành ${record.name}.`);
      }} />}
    {createOpen && canManage && <IssuingUnitForm onClose={() => setCreateOpen(false)} onSaved={(record) => {
      setCreateOpen(false); setPage(1); setSearch(""); setSearchInput(""); setStatus("all"); reload();
      void message.success(`Đã thêm đơn vị ban hành ${record.name}.`);
    }} />}
  </>;
}
