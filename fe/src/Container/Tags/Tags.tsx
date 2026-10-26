"use client";
import { useCallback, useState } from "react";
import { Alert, App, Button, Empty, Input, Space, Table } from "antd";
import { EditOutlined, EyeOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, TagsOutlined } from "@ant-design/icons";
import { listTags } from "@/apis/tagApis";
import { useAuth } from "@/context/AuthContext";
import useResource from "@/hooks/useResource";
import type { TagItem } from "@/interface/Tag/Tag.interface";
import { canManageTags } from "@/ultis/tagForm";
import { formatDate } from "@/ultis/format";
import TagDrawer from "./TagDrawer";
import TagForm from "./TagForm";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

export default function Tags() {
  const { message } = App.useApp();
  const canManage = canManageTags(useAuth());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<{ id: number; editing: boolean } | null>(null);
  const loader = useCallback((signal: AbortSignal) => listTags({
    page, itemsPerPage: pageSize, search: search || undefined,
  }, signal), [page, pageSize, search]);
  const { data, loading, error, reload } = useResource(loader);

  return <>
    <section className={styles.panel}>
      <div className={styles.heading}>
        <div className={styles.headingText}><span className={styles.headingIcon}><TagsOutlined /></span><div>
          <h2>Danh sách thẻ <span>{data?.meta?.total ?? "—"}</span></h2><p>Gắn nhãn và tổ chức văn bản theo chủ đề</p>
        </div></div>
        <div className={styles.headingActions}>
          <Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button>
          {canManage && <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>Thêm thẻ</Button>}
        </div>
      </div>
      <div className={styles.toolbar}>
        <Input.Search aria-label="Tìm thẻ" placeholder="Tìm theo tên hoặc slug…" maxLength={200} allowClear
          prefix={<SearchOutlined />} value={searchInput} onChange={(event) => setSearchInput(event.target.value)}
          onSearch={(value) => { setSearch(value.trim()); setPage(1); }} className={styles.search} />
      </div>
      {error && <Alert type="error" showIcon title={error} className={styles.error} action={<Button onClick={reload}>Thử lại</Button>} />}
      <Table<TagItem> dataSource={data?.data ?? []} loading={loading} rowKey="id" scroll={{ x: 700 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={search ? "Không tìm thấy thẻ phù hợp" : "Chưa có thẻ"} /> }}
        pagination={{ current: page, pageSize, total: data?.meta?.total ?? 0, showSizeChanger: true, pageSizeOptions: [10, 20, 50],
          showTotal: (total) => `${total} thẻ`, onChange: (next, size) => { setPage(size === pageSize ? next : 1); setPageSize(size); } }}
        columns={[
          { title: "TÊN THẺ", key: "name", render: (_, record) => <button className={styles.documentName} onClick={() => setSelected({ id: record.id, editing: false })}>
            <span><TagsOutlined /></span><div><b>{record.name}</b></div>
          </button> },
          { title: "SLUG", dataIndex: "slug", width: 240, ellipsis: true, render: (value: string) => <span className={styles.secondary}>{value}</span> },
          { title: "NGÀY TẠO", dataIndex: "created_at", width: 130, render: (value: string) => <span className={styles.secondary}>{formatDate(value)}</span> },
          { title: "THAO TÁC", key: "actions", width: canManage ? 140 : 100, fixed: "right", render: (_, record) => <Space size={4}>
            <Button type="text" icon={<EyeOutlined />} aria-label={`Xem thẻ ${record.name}`} onClick={() => setSelected({ id: record.id, editing: false })} />
            {canManage && <Button type="text" icon={<EditOutlined />} aria-label={`Sửa thẻ ${record.name}`} onClick={() => setSelected({ id: record.id, editing: true })}>Sửa</Button>}
          </Space> },
        ]} />
    </section>
    {selected && <TagDrawer key={selected.id} id={selected.id} editing={selected.editing} onClose={() => setSelected(null)}
      onEdit={() => { if (canManage) setSelected({ ...selected, editing: true }); }} onSaved={(record) => {
        setSelected(null); setPage(1); reload(); void message.success(`Đã cập nhật thẻ ${record.name}.`);
      }} />}
    {createOpen && canManage && <TagForm onClose={() => setCreateOpen(false)} onSaved={(record) => {
      setCreateOpen(false); setPage(1); setSearch(""); setSearchInput(""); reload();
      void message.success(`Đã thêm thẻ ${record.name}.`);
    }} />}
  </>;
}
