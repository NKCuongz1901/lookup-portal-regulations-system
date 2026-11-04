"use client";
import { useRef, useState } from "react";
import { Alert, Form, Input, Modal } from "antd";
import { isAxiosError } from "axios";
import { reviewField } from "@/apis/extractionApis";
import type { ExtractedField, FieldReview } from "@/interface/Extraction/Extraction.interface";
import { fieldDisplayValue } from "@/ultis/extractionReview";
import { requestError } from "@/ultis/requestError";

export default function ReviewDialog({ field, action, onClose, onSaved, onConflict }: {
  field: ExtractedField; action: FieldReview["action"]; onClose: () => void;
  onSaved: (field: ExtractedField) => void; onConflict: () => void;
}) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const request = useRef<{ signature: string; key: string } | null>(null);
  const title = action === "approve" ? "Duyệt kết quả" : action === "correct" ? "Sửa và duyệt kết quả" : "Từ chối kết quả";
  async function save(values: { value?: string; note?: string }) {
    if (saving || conflict) return;
    const body = { action, expected_revision: field.review_revision,
      ...(action === "correct" ? { corrected_value: values.value?.trim() } : {}),
      ...(values.note?.trim() ? { note: values.note.trim() } : {}) };
    const signature = JSON.stringify(body);
    if (request.current?.signature !== signature) request.current = { signature, key: crypto.randomUUID() };
    setSaving(true); setError(null);
    try { onSaved((await reviewField(field.id, { ...body, idempotency_key: request.current.key })).data); }
    catch (cause) {
      if (isAxiosError(cause) && cause.response?.status === 409) {
        setConflict(true); onConflict();
        setError("Kết quả đã thay đổi. Đóng hộp thoại, kiểm tra dữ liệu mới rồi thực hiện lại.");
      } else setError(requestError(cause));
    } finally { setSaving(false); }
  }
  return <Modal open title={title} onCancel={onClose} onOk={() => form.submit()} confirmLoading={saving}
    closable={!saving} keyboard={!saving} mask={{ closable: !saving }} cancelButtonProps={{ disabled: saving }}
    okButtonProps={{ danger: action === "reject", disabled: conflict }} okText={title} cancelText="Hủy">
    <p>Giá trị hiện tại: <b>{fieldDisplayValue(field)}</b></p>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    <Form form={form} layout="vertical" initialValues={{ value: fieldDisplayValue(field) }} disabled={saving || conflict} onFinish={(values) => void save(values)}>
      {action === "correct" && <Form.Item name="value" label="Giá trị sau chỉnh sửa" rules={[{ required: true, whitespace: true, message: "Nhập giá trị đã đối chiếu với văn bản." }, { max: 20000 }]}>
        <Input.TextArea autoSize={{ minRows: 3, maxRows: 8 }} maxLength={20000} />
      </Form.Item>}
      <Form.Item name="note" label={action === "approve" ? "Ghi chú (không bắt buộc)" : "Lý do"} rules={[{ required: action !== "approve", whitespace: true, message: "Nhập lý do để lưu vào lịch sử duyệt." }, { max: 2000 }]}>
        <Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} maxLength={2000} showCount />
      </Form.Item>
    </Form>
  </Modal>;
}
