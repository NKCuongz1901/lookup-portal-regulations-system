"use client";
import { useRef, useState } from "react";
import { Alert, Button, Drawer, Form, Input } from "antd";
import { PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import { createTag, updateTag } from "@/apis/tagApis";
import { useAuth } from "@/context/AuthContext";
import type { TagItem, TagPayload } from "@/interface/Tag/Tag.interface";
import { canManageTags, tagChanges, tagPayload, tagSlugFromName, TAG_SLUG_PATTERN } from "@/ultis/tagForm";
import { requestError } from "@/ultis/requestError";
import styles from "./Tags.module.scss";

export default function TagForm({ record, onClose, onSaved }: {
  record?: TagItem;
  onClose: () => void;
  onSaved: (record: TagItem) => void;
}) {
  const canManage = canManageTags(useAuth());
  const [form] = Form.useForm<TagPayload>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const manualSlug = useRef(false);
  const formId = record ? `edit-tag-${record.id}` : "create-tag";

  async function submit(values: TagPayload) {
    if (!canManage || pending.current) return;
    const changes = record ? tagChanges(values, record) : null;
    if (changes && !Object.keys(changes).length) { onClose(); return; }
    pending.current = true; setSubmitting(true); setError(null);
    try {
      const { data } = record && changes ? await updateTag(record.id, changes) : await createTag(tagPayload(values));
      onSaved(data);
    } catch (cause) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined;
      if (status === 409) {
        const message = "Slug đã tồn tại. Vui lòng nhập slug khác cho thẻ.";
        form.setFields([{ name: "slug", errors: [message] }]);
        form.scrollToField("slug", { focus: true }); setError(message);
      } else setError(status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : status === 403 ? "Tài khoản không có quyền thêm hoặc cập nhật thẻ."
        : status === 404 ? "Thẻ không còn tồn tại. Vui lòng làm mới danh sách."
        : requestError(cause));
    } finally { pending.current = false; setSubmitting(false); }
  }

  if (!canManage) return null;
  return <Drawer title={record ? "Sửa thẻ" : "Thêm thẻ"} open size={560}
    onClose={() => { if (!pending.current) onClose(); }} closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}
    footer={<div className={styles.footer}>
      <Button disabled={submitting} onClick={onClose}>Hủy</Button>
      <Button type="primary" icon={record ? <SaveOutlined /> : <PlusOutlined />} htmlType="submit" form={formId} loading={submitting}>
        {record ? "Lưu thay đổi" : "Thêm thẻ"}
      </Button>
    </div>}>
    {error && <Alert role="alert" type="error" showIcon title={error} className={styles.error} />}
    <Form<TagPayload> id={formId} form={form} layout="vertical" onFinish={submit} disabled={submitting}
      initialValues={record ? tagPayload(record) : undefined} scrollToFirstError={{ focus: true }}
      onValuesChange={(changed: Partial<TagPayload>, values: TagPayload) => {
        setError(null);
        if ("slug" in changed) manualSlug.current = true;
        if (!record && "name" in changed && !manualSlug.current) form.setFieldsValue({ slug: tagSlugFromName(values.name || "") });
      }}>
      <Form.Item name="name" label="Tên thẻ" rules={[
        { required: true, whitespace: true, message: "Vui lòng nhập tên thẻ." },
        { max: 100, message: "Tên thẻ không quá 100 ký tự." },
      ]}><Input autoFocus maxLength={100} placeholder="Ví dụ: Đào tạo" /></Form.Item>
      <Form.Item name="slug" label="Slug" extra="Mã duy nhất của thẻ, chỉ gồm chữ thường không dấu, số và dấu gạch ngang. Khi tạo mới, slug được gợi ý từ tên và bạn có thể sửa lại."
        rules={[
          { required: true, whitespace: true, message: "Vui lòng nhập slug." },
          { max: 120, message: "Slug không quá 120 ký tự." },
          { pattern: TAG_SLUG_PATTERN, transform: (value: string) => value?.trim(), message: "Dùng định dạng như dao-tao hoặc quy-dinh-2026; không có gạch ngang ở đầu, cuối hoặc liên tiếp." },
        ]}><Input maxLength={120} placeholder="Ví dụ: dao-tao" autoCapitalize="none" autoCorrect="off" spellCheck={false} /></Form.Item>
    </Form>
  </Drawer>;
}
