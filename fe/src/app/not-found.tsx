"use client";
import { Button, Result } from "antd";
export default function NotFound() { return <Result status="404" title="Không tìm thấy trang" subTitle="Trang bạn đang tìm không tồn tại hoặc đã được thay đổi." extra={<Button type="primary" href="/dashboard">Về tổng quan</Button>} />; }
