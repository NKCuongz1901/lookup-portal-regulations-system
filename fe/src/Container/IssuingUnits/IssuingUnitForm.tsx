"use client";
import { useRef, useState } from "react";
import { Alert, Button, Drawer, Form, Input, Switch } from "antd";
import { PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { createIssuingUnit, updateIssuingUnit } from "@/apis/issuingUnitApis";
import { useAuth } from "@/context/AuthContext";
import type { IssuingUnit, IssuingUnitPayload } from "@/interface/IssuingUnit/IssuingUnit.interface";
import { canManageIssuingUnits, issuingUnitChanges, issuingUnitPayload } from "@/ultis/issuingUnitForm";
import { requestError } from "@/ultis/requestError";
import styles from "./IssuingUnits.module.scss";

export default function IssuingUnitForm({ record, onClose, onSaved }: {
  record?: IssuingUnit;
  onClose: () => void;
  onSaved: (record: IssuingUnit) => void;
}) {
  const canManage = canManageIssuingUnits(useAuth());
  const [form] = Form.useForm<IssuingUnitPayload>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const formId = record ? `edit-issuing-unit-${record.id}` : "create-issuing-unit";

  async function submit(values: IssuingUnitPayload) {
    if (!canManage || pending.current) return;
    const changes = record ? issuingUnitChanges(values, record) : null;
    if (changes && !Object.keys(changes).length) { onClose(); return; }
    pending.current = true; setSubmitting(true); setError(null);
    try {
      const { data } = record && changes ? await updateIssuingUnit(record.id, changes)
        : await createIssuingUnit(issuingUnitPayload(values));
      onSaved(data);
    } catch (cause) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      if (status === 409) {
        const message = "Mã đơn vị ban hành đã tồn tại. Vui lòng nhập mã khác.";
        form.setFields([{ name: "code", errors: [message] }]);
        form.scrollToField("code", { focus: true }); setError(message);
      } else setError(status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : status === 403 ? "Chỉ quản trị viên được thêm hoặc cập nhật đơn vị ban hành."
        : status === 404 ? "Đơn vị ban hành không còn tồn tại. Vui lòng làm mới danh sách."
        : requestError(cause));
    } finally { pending.current = false; setSubmitting(false); }
  }

  if (!canManage) return null;
  return <Drawer title={record ? "Sửa đơn vị ban hành" : "Thêm đơn vị ban hành"} open size={560}
    onClose={() => { if (!pending.current) onClose(); }} closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}
    footer={<div className={styles.footer}>
      <Button disabled={submitting} onClick={onClose}>Hủy</Button>
      <Button type="primary" icon={record ? <SaveOutlined /> : <PlusOutlined />} htmlType="submit" form={formId} loading={submitting}>
        {record ? "Lưu thay đổi" : "Thêm đơn vị ban hành"}
      </Button>
    </div>}>
    {error && <Alert role="alert" type="error" showIcon title={error} className={styles.error} />}
    <Form<IssuingUnitPayload> id={formId} form={form} layout="vertical" onFinish={submit} disabled={submitting}
      initialValues={record ? issuingUnitPayload(record) : { is_active: true, description: null }}
      onValuesChange={() => setError(null)} scrollToFirstError={{ focus: true }}>
      <Form.Item name="code" label="Mã đơn vị ban hành" rules={[
        { required: true, whitespace: true, message: "Vui lòng nhập mã đơn vị ban hành." },
        { max: 50, message: "Mã đơn vị ban hành không quá 50 ký tự." },
      ]}><Input autoFocus maxLength={50} placeholder="Ví dụ: PDT" /></Form.Item>
      <Form.Item name="name" label="Tên đơn vị ban hành" rules={[
        { required: true, whitespace: true, message: "Vui lòng nhập tên đơn vị ban hành." },
        { max: 255, message: "Tên đơn vị ban hành không quá 255 ký tự." },
      ]}><Input maxLength={255} placeholder="Ví dụ: Phòng Đào tạo" /></Form.Item>
      <Form.Item name="description" label="Mô tả"><Input.TextArea rows={4} placeholder="Thông tin về đơn vị ban hành" /></Form.Item>
      <Form.Item name="is_active" label="Trạng thái" valuePropName="checked"
        extra="Đơn vị ngừng sử dụng sẽ không được chọn cho văn bản mới. Các văn bản đã gắn đơn vị này vẫn giữ nguyên.">
        <Switch checkedChildren="Đang sử dụng" unCheckedChildren="Ngừng sử dụng" />
      </Form.Item>
    </Form>
  </Drawer>;
}
