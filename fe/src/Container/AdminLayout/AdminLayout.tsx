"use client";
import { useState } from "react";
import type { ReactNode } from "react";
import { App, Avatar, Button, Drawer, Dropdown, Menu, Tooltip } from "antd";
import { CalendarOutlined, DownOutlined, FileTextOutlined, LogoutOutlined, MenuOutlined, SearchOutlined, TeamOutlined } from "@ant-design/icons";
import { usePathname, useRouter } from "next/navigation";
import Brand from "@/Components/Brand/Brand";
import { useAuth } from "@/context/AuthContext";
import { logout } from "@/apis/authApis";
import { initials } from "@/ultis/format";
import { requestError } from "@/ultis/requestError";
import { mainRoutes } from "@/routes/MainRoutes";
import styles from "./AdminLayout.module.scss";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const user = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { modal, message } = App.useApp();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const role = user.roles.includes("ADMIN") ? "Quản trị viên" : "Nhân viên";
  const title = pathname === mainRoutes.users ? "Người dùng" : pathname === mainRoutes.documents ? "Văn bản" : "Tổng quan";
  const date = new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
  async function signOut() {
    setLoggingOut(true);
    try { await logout(); window.location.replace(mainRoutes.login); }
    catch (error) { message.error(requestError(error)); setLoggingOut(false); }
  }
  function showAccount() {
    modal.info({ title: "Tài khoản của bạn", centered: true, okText: "Đóng", content: <div className={styles.accountDetails}><b>{user.full_name}</b><p>{user.email}</p><span>{role}</span></div> });
  }
  const sidebar = <div className={styles.sidebarInner}>
    <Brand />
    <Dropdown trigger={["click"]} menu={{ items: [
      { key: "account", label: "Thông tin tài khoản", onClick: showAccount },
      { key: "logout", label: "Đăng xuất", icon: <LogoutOutlined />, onClick: signOut },
    ] }}>
      <button className={styles.profile} aria-label="Mở menu tài khoản">
        <Avatar size={39} className={styles.avatar}>{initials(user.full_name)}</Avatar>
        <span className={styles.profileText}><b>{user.full_name}</b><small>{role}</small></span><DownOutlined />
      </button>
    </Dropdown>
    <div className={styles.navLabel}>QUẢN LÝ</div>
    <nav aria-label="Điều hướng chính">
      <Menu mode="inline" selectedKeys={[pathname]} items={[
        { key: mainRoutes.users, icon: <TeamOutlined />, label: "Người dùng" },
        { key: mainRoutes.documents, icon: <FileTextOutlined />, label: "Văn bản" },
      ]} onClick={({ key }) => { router.push(key); setMobileOpen(false); }} />
    </nav>
    <div className={styles.sidebarBottom}>
      <div className={styles.workspace}><span className={styles.workspaceIcon}>R</span><div><b>Không gian quản trị</b><small>Regula Workspace</small></div><span className={styles.onlineDot} /></div>
      <Button type="text" block icon={<LogoutOutlined />} loading={loggingOut} onClick={signOut} className={styles.logout}>Đăng xuất</Button>
      <span className={styles.version}>REGULA · VĂN BẢN & QUY ĐỊNH</span>
    </div>
  </div>;
  return <div className={styles.frame}>
    <aside className={styles.sidebar}>{sidebar}</aside>
    <Drawer title="Điều hướng" placement="left" open={mobileOpen} onClose={() => setMobileOpen(false)} size={280} styles={{ body: { padding: 0 } }}>{sidebar}</Drawer>
    <div className={styles.main}>
      <header className={styles.header}>
        <div className={styles.headerTitle}>
          <Button className={styles.mobileToggle} icon={<MenuOutlined />} type="text" onClick={() => setMobileOpen(true)} aria-label="Mở điều hướng" />
          <div><span className={styles.breadcrumb}>Không gian quản trị <span>/</span> {title}</span><h1>{title}</h1><p>{pathname === mainRoutes.dashboard ? `Chào ${user.full_name.split(" ").at(-1)}, chúc bạn một ngày làm việc hiệu quả.` : pathname === mainRoutes.users ? "Danh sách tài khoản và quyền truy cập hệ thống." : "Tập trung văn bản, quy định và thông tin của đơn vị."}</p></div>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.date}><CalendarOutlined /> {date}</span>
          <Tooltip title="Tìm kiếm văn bản"><Button type="text" shape="circle" icon={<SearchOutlined />} onClick={() => router.push(mainRoutes.documents)} aria-label="Tìm kiếm văn bản" /></Tooltip>
          <button onClick={showAccount} className={styles.headerAvatar} aria-label="Thông tin tài khoản"><Avatar className={styles.avatar} size={35}>{initials(user.full_name)}</Avatar></button>
        </div>
      </header>
      <main className={styles.content}>{children}</main>
      <footer className={styles.footer}><span>Regula · Cổng quản trị văn bản</span><span>Thông tin tập trung. Công việc liền mạch.</span></footer>
    </div>
  </div>;
}
