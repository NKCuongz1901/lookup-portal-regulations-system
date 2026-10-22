"use client";

import { useRef, useState } from "react";
import { Alert, Button, DatePicker, Divider, Drawer, Form, Input, Select } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import type { Dayjs } from "dayjs";
import { createDocument, getDocumentCreateOptions } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentCreatePayload, DocumentDetail } from "@/interface/Document/Document.interface";
import { requestError } from "@/ultis/requestError";
import styles from "./CreateDocument.module.scss";

interface FormValues extends Omit<DocumentCreatePayload, "issue_date" | "effective_from" | "effective_until"> {
  issue_date?: Dayjs | null;
  effective_from?: Dayjs | null;
  effective_until?: Dayjs | null;
}

export default function CreateDocument({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (document: DocumentDetail) => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const { data: options, loading: loadingOptions, error: optionsError, reload } = useResource(getDocumentCreateOptions);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);

  async function submit(values: FormValues) {
    if (pending.current) return;
    pending.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const result = await createDocument({
        ...values,
        code: values.code.trim(), title: values.title.trim(),
        description: values.description?.trim() || null,
        academic_year: values.academic_year?.trim() || null,
        document_type_id: values.document_type_id ?? null,
        issuing_unit_id: values.issuing_unit_id ?? null,
        issue_date: values.issue_date?.format("YYYY-MM-DD") ?? null,
        effective_from: values.effective_from?.format("YYYY-MM-DD") ?? null,
        effective_until: values.effective_until?.format("YYYY-MM-DD") ?? null,
        applicable_subject_codes: [...new Set((values.applicable_subject_codes ?? []).map((code) => code.trim()).filter(Boolean))],
        tag_ids: values.tag_ids ?? [],
      });
      onCreated(result.data);
    } catch (cause) {
      if (isAxiosError(cause) && cause.response?.status === 409) {
        const message = "Mã văn bản đã tồn tại. Vui lòng nhập mã khác.";
        form.setFields([{ name: "code", errors: [message] }]);
        form.scrollToField("code", { focus: true });
        setError(message);
      } else {
        setError(requestError(cause));
      }
    } finally {
      pending.current = false;
      setSubmitting(false);
    }
  }

  return <Drawer title="Tạo văn bản" open size={680} onClose={() => { if (!pending.current) onClose(); }}
    closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}
    footer={<div className={styles.footer}>
      <Button onClick={onClose} disabled={submitting}>Hủy</Button>
      <Button type="primary" icon={<PlusOutlined />} htmlType="submit" form="create-document" loading={submitting}>Tạo văn bản</Button>
    </div>}>
    <Alert className={styles.intro} type="info" showIcon title="Văn bản mới sẽ được lưu ở trạng thái Bản nháp." />
    {error && <Alert role="alert" className={styles.error} type="error" showIcon title={error} />}
    {optionsError && <Alert className={styles.error} type="warning" showIcon title="Chưa tải được danh mục. Bạn vẫn có thể tạo văn bản và bổ sung thông tin sau."
      action={<Button onClick={reload} loading={loadingOptions}>Thử lại</Button>} />}
    <Form<FormValues> id="create-document" form={form} layout="vertical" onFinish={submit} disabled={submitting}
      initialValues={{ applicable_subject_codes: [], tag_ids: [] }} scrollToFirstError={{ focus: true }}
      onValuesChange={() => setError(null)}>
      <h3 className={styles.sectionTitle}>Thông tin văn bản</h3>
      <Form.Item name="code" label="Mã văn bản" rules={[{ required: true, whitespace: true, message: "Vui lòng nhập mã văn bản." }, { max: 100 }]}>
        <Input autoFocus maxLength={100} placeholder="Ví dụ: QD-2026-001" />
      </Form.Item>
      <Form.Item name="title" label="Tên văn bản" rules={[{ required: true, whitespace: true, message: "Vui lòng nhập tên văn bản." }, { max: 500 }]}>
        <Input maxLength={500} placeholder="Nhập tên đầy đủ của văn bản" />
      </Form.Item>
      <Form.Item name="description" label="Mô tả"><Input.TextArea rows={3} placeholder="Tóm tắt nội dung văn bản" /></Form.Item>
      <div className={styles.grid}>
        <Form.Item name="document_type_id" label="Loại văn bản"><Select allowClear showSearch optionFilterProp="label"
          loading={loadingOptions} disabled={submitting || !options} placeholder="Chọn loại văn bản"
          options={options?.types.map((item) => ({ value: item.id, label: item.name }))} notFoundContent="Chưa có loại văn bản" /></Form.Item>
        <Form.Item name="issuing_unit_id" label="Đơn vị ban hành"><Select allowClear showSearch optionFilterProp="label"
          loading={loadingOptions} disabled={submitting || !options} placeholder="Chọn đơn vị ban hành"
          options={options?.units.map((item) => ({ value: item.id, label: item.name }))} notFoundContent="Chưa có đơn vị ban hành" /></Form.Item>
      </div>
      <Divider />
      <h3 className={styles.sectionTitle}>Thời gian và phạm vi áp dụng</h3>
      <div className={styles.grid}>
        <Form.Item name="issue_date" label="Ngày ban hành"><DatePicker className={styles.date} format="DD/MM/YYYY" placeholder="Chọn ngày" /></Form.Item>
        <Form.Item name="academic_year" label="Năm học" rules={[{ max: 30 }]}><Input maxLength={30} placeholder="Ví dụ: 2026-2027" /></Form.Item>
        <Form.Item name="effective_from" label="Có hiệu lực từ"><DatePicker className={styles.date} format="DD/MM/YYYY" placeholder="Chọn ngày" /></Form.Item>
        <Form.Item name="effective_until" label="Có hiệu lực đến" dependencies={["effective_from"]} rules={[
          ({ getFieldValue }) => ({ validator(_, value: Dayjs | undefined) {
            const start = getFieldValue("effective_from") as Dayjs | undefined;
            return start && value && value.isBefore(start, "day")
              ? Promise.reject(new Error("Ngày kết thúc phải từ ngày bắt đầu trở đi.")) : Promise.resolve();
          } }),
        ]}><DatePicker className={styles.date} format="DD/MM/YYYY" placeholder="Không giới hạn" /></Form.Item>
      </div>
      <Form.Item name="applicable_subject_codes" label="Đối tượng áp dụng" extra="Chọn hoặc nhập mã đối tượng, nhấn Enter để thêm.">
        <Select mode="tags" tokenSeparators={[","]} placeholder="Chọn đối tượng" options={[
          { value: "STUDENT", label: "Sinh viên" }, { value: "STAFF", label: "Nhân viên" }, { value: "ADMIN", label: "Quản trị viên" },
        ]} />
      </Form.Item>
      <Form.Item name="tag_ids" label="Thẻ"><Select mode="multiple" allowClear optionFilterProp="label" loading={loadingOptions}
        disabled={submitting || !options} placeholder="Chọn thẻ để dễ tra cứu"
        options={options?.tags.map((item) => ({ value: item.id, label: item.name }))} notFoundContent="Chưa có thẻ" /></Form.Item>
    </Form>
  </Drawer>;
}
