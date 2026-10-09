"use client";
import { useCallback, useMemo, useState } from "react";
import { Alert, Avatar, Button, Empty, Select, Skeleton, Table } from "antd";
import { ArrowRightOutlined, CheckCircleOutlined, FileTextOutlined, FormOutlined, TeamOutlined } from "@ant-design/icons";
import Link from "next/link";
import { getDashboard } from "@/apis/dashboardApis";
import useResource from "@/hooks/useResource";
import StatusTag, { publicationColors, publicationLabels } from "@/Components/StatusTag/StatusTag";
import type { DocumentItem, PublicationStatus } from "@/interface/Document/Document.interface";
import { formatDate, formatNumber, initials } from "@/ultis/format";
import styles from "./Dashboard.module.scss";

function ActivityChart({ documents, months }: { documents: DocumentItem[]; months: number }) {
  const buckets = useMemo(() => Array.from({ length: months }, (_, index) => {
    const today = new Date();
    const date = new Date(today.getFullYear(), today.getMonth() - months + index + 1, 1);
    const count = documents.filter((document) => {
      const created = new Date(document.created_at);
      return created.getFullYear() === date.getFullYear() && created.getMonth() === date.getMonth();
    }).length;
    return { label: `T${date.getMonth() + 1}`, count };
  }), [documents, months]);
  const max = Math.max(4, ...buckets.map((bucket) => bucket.count));
  const points = buckets.map((bucket, i) => ({ x: 42 + i * (490 / (months - 1)), y: 176 - bucket.count / max * 135, ...bucket }));
  const path = points.map((point, i) => `${i ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  return <div className={styles.chart}>
    <svg viewBox="0 0 560 220" role="img" aria-label={`Văn bản được tạo trong ${months} tháng gần đây: ${buckets.map((b) => `${b.label}: ${b.count}`).join(", ")}`}>
      <defs><linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2b997d" stopOpacity=".17" /><stop offset="100%" stopColor="#2b997d" stopOpacity="0.01" /></linearGradient></defs>
      {[0, 1, 2, 3, 4].map((step) => <g key={step}><line x1="42" x2="532" y1={41 + step * 33.75} y2={41 + step * 33.75} stroke="#edf0f4" /><text x="24" y={45 + step * 33.75} textAnchor="end">{Math.round(max * (1 - step / 4))}</text></g>)}
      <path d={`${path} L 532 176 L 42 176 Z`} fill="url(#activity-fill)" />
      <path d={path} fill="none" stroke="#2b997d" strokeWidth="2.5" strokeLinejoin="round" />
      {points.map((point, index) => <g key={index}><circle cx={point.x} cy={point.y} r="4" fill="white" stroke="#2b997d" strokeWidth="2"><title>{point.label}: {point.count} văn bản</title></circle><text x={point.x} y="206" textAnchor="middle">{point.label}</text></g>)}
    </svg>
    {!documents.length && <span className={styles.chartEmpty}>Văn bản mới sẽ xuất hiện tại đây</span>}
  </div>;
}

export default function Dashboard() {
  const loader = useCallback((signal: AbortSignal) => getDashboard(signal), []);
  const { data, loading, error, reload } = useResource(loader);
  const [months, setMonths] = useState(6);
  if (error) return <Alert type="error" showIcon title={error} action={<Button onClick={reload}>Thử lại</Button>} />;
  if (loading || !data) return <div className={styles.skeleton}><Skeleton active paragraph={{ rows: 3 }} /><Skeleton active paragraph={{ rows: 8 }} /></div>;
  const metrics = [
    { label: "Tổng văn bản", count: data.documentCount, icon: <FileTextOutlined />, note: "Toàn bộ văn bản trong hệ thống", href: "/documents", color: "blue" },
    { label: "Đã công bố", count: data.counts.published, icon: <CheckCircleOutlined />, note: "Sẵn sàng để tra cứu", href: "/documents?status=published", color: "green" },
    { label: "Bản nháp", count: data.counts.draft, icon: <FormOutlined />, note: "Đang được chuẩn bị", href: "/documents?status=draft", color: "amber" },
    { label: "Người dùng", count: data.userCount, icon: <TeamOutlined />, note: "Tài khoản trong hệ thống", href: "/users", color: "blue" },
  ];
  let offset = 0;
  const stops = (Object.keys(data.counts) as PublicationStatus[]).map((status) => {
    const start = offset;
    offset += data.documentCount ? data.counts[status] / data.documentCount * 100 : 0;
    return `${publicationColors[status]} ${start}% ${offset}%`;
  });
  return <div className={styles.dashboard}>
    <section className={styles.metrics} aria-label="Thống kê tổng quan">
      {metrics.map((metric) => <Link href={metric.href} className={styles.metric} key={metric.label}>
        <div className={styles.metricTop}><span>{metric.label}</span><span className={`${styles.metricIcon} ${styles[metric.color]}`}>{metric.icon}</span></div>
        <div className={styles.metricValue}>{formatNumber(metric.count)}<ArrowRightOutlined /></div>
        <div className={styles.metricNote}>{metric.note}</div>
      </Link>)}
    </section>
    <div className={styles.chartRow}>
      <section className={styles.panel}>
        <div className={styles.panelHeading}><div><h2>Hoạt động văn bản</h2><p>Số văn bản được tạo theo tháng</p></div><Select aria-label="Khoảng thời gian biểu đồ" value={months} onChange={setMonths} options={[{ value: 6, label: "6 tháng gần đây" }, { value: 12, label: "12 tháng gần đây" }]} size="small" /></div>
        <div className={styles.legend}><span /> Văn bản được tạo</div>
        <ActivityChart documents={data.recent} months={months} />
        <div className={styles.chartFootnote}>Thống kê từ tối đa 100 văn bản gần nhất, không gồm lưu trữ.</div>
      </section>
      <section className={styles.panel}>
        <div className={styles.panelHeading}><div><h2>Trạng thái văn bản</h2><p>Phân bố trong toàn hệ thống</p></div><FileTextOutlined className={styles.headingIcon} /></div>
        <div className={styles.donut} style={{ background: data.documentCount ? `conic-gradient(${stops.join(",")})` : "#eef2f7" }} role="img" aria-label={`Tổng ${data.documentCount} văn bản`}><div><b>{formatNumber(data.documentCount)}</b><span>Tổng văn bản</span></div></div>
        <div className={styles.distribution}>{(Object.keys(data.counts) as PublicationStatus[]).map((status) => <Link key={status} href={`/documents?status=${status}`}><span style={{ background: publicationColors[status] }} /><span>{publicationLabels[status]}</span><b>{formatNumber(data.counts[status])}</b></Link>)}</div>
      </section>
    </div>
    <div className={styles.bottomRow}>
      <section className={`${styles.panel} ${styles.recentPanel}`}>
        <div className={styles.panelHeading}><div><h2>Văn bản gần đây</h2><p>Theo dõi những văn bản mới nhất</p></div><Link href="/documents" className={styles.viewAll}>Xem tất cả <ArrowRightOutlined /></Link></div>
        <Table<DocumentItem> dataSource={data.recent.slice(0, 5)} rowKey="id" pagination={false} size="small" scroll={{ x: 500 }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có văn bản nào" /> }} columns={[
          { title: "TÊN VĂN BẢN", key: "title", render: (_, record) => <Link className={styles.documentName} href={`/documents?id=${record.id}`}><span><FileTextOutlined /></span><div><b>{record.title}</b><small>{record.code}</small></div></Link> },
          { title: "NGÀY TẠO", dataIndex: "created_at", width: 100, render: formatDate },
          { title: "TRẠNG THÁI", dataIndex: "publication_status", width: 120, render: (status) => <StatusTag status={status} /> },
        ]} />
      </section>
      <section className={styles.panel}>
        <div className={styles.panelHeading}><div><h2>Người dùng</h2><p>Cùng làm việc, cùng kết nối</p></div><Link href="/users" aria-label="Xem tất cả người dùng" className={styles.viewAll}><ArrowRightOutlined /></Link></div>
        <div className={styles.people}>{data.users.length ? data.users.map((user) => <div className={styles.person} key={user.id}><Avatar size={36}>{initials(user.full_name)}</Avatar><div><b>{user.full_name}</b><span>{user.roles.includes("ADMIN") ? "Quản trị viên" : user.roles.includes("STAFF") ? "Nhân viên" : "Sinh viên"}</span></div><i className={user.is_active ? styles.activeDot : styles.inactiveDot} /></div>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có người dùng" />}</div>
        <Link href="/users" className={styles.peopleLink}>Quản lý người dùng <ArrowRightOutlined /></Link>
      </section>
    </div>
  </div>;
}
