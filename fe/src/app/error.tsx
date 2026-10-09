"use client";
import { Button, Result } from "antd";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <Result status="warning" title="Chưa thể kết nối hệ thống" subTitle="Vui lòng kiểm tra kết nối và thử lại sau ít phút." extra={<><Button type="primary" onClick={reset}>Thử lại</Button><Button href="/login">Về đăng nhập</Button></>} />;
}
