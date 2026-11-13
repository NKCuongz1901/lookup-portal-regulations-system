"use client";
import { useCallback, useState } from "react";
import { Alert, Avatar, Badge, Button, Descriptions, Drawer, Empty, Input, Table, Tabs, Tag } from "antd";
import { EyeOutlined, ReloadOutlined, SearchOutlined, TeamOutlined } from "@ant-design/icons";
import { getUsers } from "@/apis/userApis";
import useResource from "@/hooks/useResource";
import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import { initials } from "@/ultis/format";
import styles from "@/Components/DataPanel/DataPanel.module.scss";

type UserRoleTab = "STUDENT" | "STAFF";

const roleNames = { ADMIN: "Quản trị viên", STAFF: "Nhân viên", STUDENT: "Sinh viên" };
const tabLabels: Record<UserRoleTab, string> = {
  STUDENT: "Sinh viên",
  STAFF: "Nhân viên",
};

export default function Users() {
  const [role, setRole] = useState<UserRoleTab>("STUDENT");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<CurrentUser | null>(null);

  const loader = useCallback(
    (signal: AbortSignal) =>
      getUsers(
        { page, itemsPerPage: pageSize, search: search || undefined, role },
        signal,
      ),
    [page, pageSize, search, role],
  );
  const { data, loading, error, reload } = useResource(loader);

  return (
    <>
      <section className={styles.panel}>
        <div className={styles.heading}>
          <div className={styles.headingText}>
            <span className={styles.headingIcon}>
              <TeamOutlined />
            </span>
            <div>
              <h2>
                Danh sách người dùng <span>{data?.meta?.total ?? "—"}</span>
              </h2>
              <p>Tài khoản được cấp quyền trong hệ thống</p>
            </div>
          </div>
          <Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>
            Làm mới
          </Button>
        </div>

        <Tabs
          activeKey={role}
          onChange={(key) => {
            setRole(key as UserRoleTab);
            setPage(1);
            setSelected(null);
          }}
          items={[
            { key: "STUDENT", label: tabLabels.STUDENT },
            { key: "STAFF", label: tabLabels.STAFF },
          ]}
        />

        <div className={styles.toolbar}>
          <Input.Search
            aria-label="Tìm người dùng"
            placeholder={
              role === "STUDENT"
                ? "Tìm theo email hoặc mã sinh viên…"
                : "Tìm theo email…"
            }
            allowClear
            prefix={<SearchOutlined />}
            onSearch={(value) => {
              setSearch(value.trim());
              setPage(1);
            }}
            className={styles.search}
          />
          <span className={styles.toolbarNote}>
            Đang xem: {tabLabels[role]}
          </span>
        </div>

        {error && (
          <Alert
            type="error"
            showIcon
            title={error}
            className={styles.error}
            action={<Button onClick={reload}>Thử lại</Button>}
          />
        )}

        <Table<CurrentUser>
          dataSource={data?.data || []}
          loading={loading}
          rowKey="id"
          scroll={{ x: 760 }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  search
                    ? "Không tìm thấy người dùng phù hợp"
                    : `Chưa có ${tabLabels[role].toLowerCase()}`
                }
              />
            ),
          }}
          pagination={{
            current: page,
            pageSize,
            total: data?.meta?.total || 0,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50],
            showTotal: (total) =>
              `${total} ${tabLabels[role].toLowerCase()}`,
            onChange: (next, size) => {
              setPage(size === pageSize ? next : 1);
              setPageSize(size);
            },
          }}
          columns={[
            {
              title: "NGƯỜI DÙNG",
              dataIndex: "full_name",
              render: (_, user) => (
                <button
                  className={styles.userName}
                  onClick={() => setSelected(user)}
                >
                  <Avatar className={styles.avatar} size={37}>
                    {initials(user.full_name)}
                  </Avatar>
                  <span>
                    <b>{user.full_name}</b>
                    <small>ID: {user.id}</small>
                  </span>
                </button>
              ),
            },
            {
              title: "EMAIL",
              dataIndex: "email",
              render: (email) => (
                <span className={styles.secondary}>{email}</span>
              ),
            },
            ...(role === "STUDENT"
              ? [
                  {
                    title: "MÃ SV",
                    dataIndex: "student_code" as const,
                    render: (code: string | null) => (
                      <span className={styles.secondary}>
                        {code || "—"}
                      </span>
                    ),
                  },
                ]
              : []),
            {
              title: "VAI TRÒ",
              dataIndex: "roles",
              render: (roles: CurrentUser["roles"]) =>
                roles.map((r) => (
                  <Tag
                    key={r}
                    variant="filled"
                    color={
                      r === "ADMIN" ? "blue" : r === "STAFF" ? "cyan" : "default"
                    }
                  >
                    {roleNames[r]}
                  </Tag>
                )),
            },
            {
              title: "TRẠNG THÁI",
              dataIndex: "is_active",
              render: (active: boolean) => (
                <Badge
                  status={active ? "success" : "default"}
                  text={
                    <span className={styles.secondary}>
                      {active ? "Hoạt động" : "Đã vô hiệu hóa"}
                    </span>
                  }
                />
              ),
            },
            {
              title: "",
              key: "action",
              width: 50,
              render: (_: unknown, user: CurrentUser) => (
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  aria-label={`Xem ${user.full_name}`}
                  onClick={() => setSelected(user)}
                />
              ),
            },
          ]}
        />
      </section>

      <Drawer
        title="Thông tin người dùng"
        open={!!selected}
        onClose={() => setSelected(null)}
        size={460}
      >
        {selected && (
          <>
            <div className={styles.detailIdentity}>
              <Avatar size={60} className={styles.avatar}>
                {initials(selected.full_name)}
              </Avatar>
              <h2>{selected.full_name}</h2>
              <p>{selected.email}</p>
            </div>
            <Descriptions
              column={1}
              layout="vertical"
              items={[
                {
                  key: "role",
                  label: "Vai trò",
                  children: selected.roles
                    .map((r) => roleNames[r])
                    .join(", "),
                },
                {
                  key: "student",
                  label: "Mã sinh viên",
                  children: selected.student_code || "Không áp dụng",
                },
                {
                  key: "active",
                  label: "Trạng thái",
                  children: selected.is_active
                    ? "Đang hoạt động"
                    : "Đã vô hiệu hóa",
                },
              ]}
            />
          </>
        )}
      </Drawer>
    </>
  );
}
