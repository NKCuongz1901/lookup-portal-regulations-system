"use client";
import { useRef, useState } from "react";
import { Alert, Button, Drawer, Form, Input, Switch } from "antd";
import { PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { createDocumentType, updateDocumentType } from "@/apis/documentTypeApis";
import { useAuth } from "@/context/AuthContext";
import type { DocumentType, DocumentTypePayload } from "@/interface/DocumentType/DocumentType.interface";
import { canManageDocumentTypes, documentTypeChanges, documentTypePayload } from "@/ultis/documentTypeForm";
import { requestError } from "@/ultis/requestError";
import styles from "./DocumentTypes.module.scss";

export default function DocumentTypeForm({ record, onClose, onSaved }: {
  record?: DocumentType;
  onClose: () => void;
  onSaved: (record: DocumentType) => void;
}) {
  const canManage = canManageDocumentTypes(useAuth());
  const [form] = Form.useForm<DocumentTypePayload>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const formId = record ? `edit-document-type-${record.id}` : "create-document-type";

  async function submit(values: DocumentTypePayload) {
    if (!canManage || pending.current) return;
    const changes = record ? documentTypeChanges(values, record) : null;
    if (changes && !Object.keys(changes).length) { onClose(); return; }
    pending.current = true; setSubmitting(true); setError(null);
    try {
      const { data } = record && changes ? await updateDocumentType(record.id, changes)
        : await createDocumentType(documentTypePayload(values));
      onSaved(data);
    } catch (cause) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      if (status === 409) {
        const message = "Mã loại văn bản đã tồn tại. Vui lòng nhập mã khác.";
        form.setFields([{ name: "code", errors: [message] }]);
        form.scrollToField("code", { focus: true }); setError(message);
      } else setError(status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : status === 403 ? "Chỉ quản trị viên được thêm hoặc cập nhật loại văn bản."
        : status === 404 ? "Loại văn bản không còn tồn tại. Vui lòng làm mới danh sách."
        : requestError(cause));
    } finally { pending.current = false; setSubmitting(false); }
  }

  if (!canManage) return null;
  return <Drawer title={record ? "Sửa loại văn bản" : "Thêm loại văn bản"} open size={560}
    onClose={() => { if (!pending.current) onClose(); }} closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}
    footer={<div className={styles.footer}>
      <Button disabled={submitting} onClick={onClose}>Hủy</Button>
      <Button type="primary" icon={record ? <SaveOutlined /> : <PlusOutlined />} htmlType="submit" form={formId} loading={submitting}>
        {record ? "Lưu thay đổi" : "Thêm loại văn bản"}
      </Button>
    </div>}>
    {error && <Alert role="alert" type="error" showIcon title={error} className={styles.error} />}
    <Form<DocumentTypePayload> id={formId} form={form} layout="vertical" onFinish={submit} disabled={submitting}
      initialValues={record ? documentTypePayload(record) : { is_active: true, description: null }}
      onValuesChange={() => setError(null)} scrollToFirstError={{ focus: true }}>
      <Form.Item name="code" label="Mã loại văn bản" rules={[
        { required: true, whitespace: true, message: "Vui lòng nhập mã loại văn bản." },
        { max: 50, message: "Mã loại văn bản không quá 50 ký tự." },
      ]}><Input autoFocus maxLength={50} placeholder="Ví dụ: QUY_DINH" /></Form.Item>
      <Form.Item name="name" label="Tên loại văn bản" rules={[
        { required: true, whitespace: true, message: "Vui lòng nhập tên loại văn bản." },
        { max: 150, message: "Tên loại văn bản không quá 150 ký tự." },
      ]}><Input maxLength={150} placeholder="Ví dụ: Quy định" /></Form.Item>
      <Form.Item name="description" label="Mô tả"><Input.TextArea rows={4} placeholder="Mô tả cách sử dụng loại văn bản này" /></Form.Item>
      <Form.Item name="is_active" label="Trạng thái" valuePropName="checked"
        extra="Loại ngừng sử dụng sẽ không được chọn cho văn bản mới. Các văn bản đã gắn loại này vẫn giữ nguyên.">
        <Switch checkedChildren="Đang sử dụng" unCheckedChildren="Ngừng sử dụng" />
      </Form.Item>
    </Form>
  </Drawer>;
}
