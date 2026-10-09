"use client";
import { Alert, App, Button, Checkbox, Form, Input } from "antd";
import { ArrowRightOutlined, CheckOutlined, FileTextOutlined, LockOutlined, MailOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { useSearchParams } from "next/navigation";
import Brand from "@/Components/Brand/Brand";
import useLogin from "@/hooks/Login/useLogin";
import type { LoginPayload } from "@/interface/Auth/Auth.interface";
import styles from "./Login.module.scss";

export default function Login() {
  const { loading, error, onLogin, clearError } = useLogin();
  const { modal } = App.useApp();
  const search = useSearchParams();
  const help = () => modal.info({ title: "Hỗ trợ truy cập", okText: "Đã hiểu", centered: true,
    content: "Nếu quên mật khẩu hoặc chưa có tài khoản, vui lòng liên hệ quản trị viên của đơn vị để được cấp lại thông tin đăng nhập.",
  });
  return <main className={styles.page}>
    <aside className={styles.intro}>
      <Brand light href="/login" />
      <div className={styles.introContent}>
        <span className={styles.eyebrow}>CỔNG QUẢN TRỊ VĂN BẢN</span>
        <h1>Thông tin rõ ràng.<br />Quản lý dễ dàng.</h1>
        <p>Kết nối văn bản, quy định và con người<br /> trong một không gian làm việc.</p>
        <div className={styles.illustration} aria-hidden="true">
          <div className={styles.orbit} /><div className={styles.backSheet} />
          <div className={styles.documentCard}>
            <div className={styles.docHead}><span><FileTextOutlined /></span><i /><b>REGULA</b></div>
            <div className={styles.docTitle}>Quy chế & quy định</div>
            <div className={styles.docCaption}>Thông tin được tổ chức, công việc được kết nối.</div>
            <div className={styles.docLines}><i /><i /><i /></div>
            <div className={styles.docFooter}><span><CheckOutlined /> Nhất quán</span><span><CheckOutlined /> Dễ tra cứu</span></div>
          </div>
          <div className={styles.floatingBadge}><SafetyCertificateOutlined /><div><b>Đúng người, đúng quyền</b><span>Không gian làm việc an toàn</span></div></div>
        </div>
      </div>
      <div className={styles.introFooter}><span className={styles.tinyDot} /> Đồng hành cùng công tác quản lý giáo dục</div>
    </aside>
    <section className={styles.formSide} aria-labelledby="login-title">
      <div className={styles.topBar}><span>Không gian quản trị</span><Button type="text" onClick={help}>Cần hỗ trợ? <ArrowRightOutlined /></Button></div>
      <div className={styles.formWrap}>
        <div className={styles.mobileBrand}><Brand href="/login" /></div>
        <div className={styles.accessBadge}><SafetyCertificateOutlined /> Dành cho Admin & Staff</div>
        <h2 id="login-title">Chào mừng trở lại<span>.</span></h2>
        <p className={styles.subtitle}>Đăng nhập để bắt đầu ngày làm việc của bạn.</p>
        {search.get("expired") && !error && <Alert className={styles.alert} type="info" showIcon title="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại." />}
        {error && <Alert className={styles.alert} type="error" showIcon title={error} />}
        <Form<LoginPayload> layout="vertical" requiredMark={false} onFinish={onLogin} onValuesChange={clearError} initialValues={{ remember: true }} size="large" disabled={loading}>
          <Form.Item name="email" label="Địa chỉ email" rules={[{ required: true, message: "Vui lòng nhập email." }, { type: "email", message: "Địa chỉ email chưa hợp lệ." }]} normalize={(value: string) => value.trim()}>
            <Input prefix={<MailOutlined />} placeholder="ban@truong.edu.vn" autoComplete="username" inputMode="email" maxLength={255} />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: "Vui lòng nhập mật khẩu." }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Nhập mật khẩu của bạn" autoComplete="current-password" />
          </Form.Item>
          <div className={styles.formOptions}>
            <Form.Item name="remember" valuePropName="checked" noStyle><Checkbox>Ghi nhớ đăng nhập</Checkbox></Form.Item>
            <Button type="link" onClick={help}>Quên mật khẩu?</Button>
          </div>
          <Button className={styles.submit} type="primary" htmlType="submit" block loading={loading}>Đăng nhập <ArrowRightOutlined /></Button>
        </Form>
        <div className={styles.accessNote}><LockOutlined /><span>Chỉ dành cho tài khoản được đơn vị cấp quyền quản trị.</span></div>
      </div>
      <footer className={styles.footer}><span>Regula · Hệ thống quản lý văn bản</span><span>Đơn giản. Tập trung. Hiệu quả.</span></footer>
    </section>
  </main>;
}
