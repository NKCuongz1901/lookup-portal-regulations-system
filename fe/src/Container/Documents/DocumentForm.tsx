"use client";

import { useRef, useState } from "react";
import { Alert, Button, DatePicker, Divider, Drawer, Form, Input, Select } from "antd";
import { PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { isAxiosError } from "axios";
import type { Dayjs } from "dayjs";
import { createDocument, getDocumentCreateOptions, updateDocument } from "@/apis/documentApis";
import useResource from "@/hooks/useResource";
import type { DocumentDetail } from "@/interface/Document/Document.interface";
import { requestError } from "@/ultis/requestError";
import { documentFormPayload, documentInitialValues, documentUpdatePayload, includeCurrentOptions, type DocumentFormValues } from "@/ultis/documentForm";
import styles from "./CreateDocument.module.scss";

export default function DocumentForm({ document, onClose, onSaved }: {
  document?: DocumentDetail;
  onClose: () => void;
  onSaved: (document: DocumentDetail) => void;
}) {
  const [form] = Form.useForm<DocumentFormValues>();
  const { data: options, loading: loadingOptions, error: optionsError, reload } = useResource(getDocumentCreateOptions);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const formId = document ? `edit-document-${document.id}` : "create-document";
  const types = includeCurrentOptions(options?.types, document?.document_type ? [document.document_type] : []);
  const units = includeCurrentOptions(options?.units, document?.issuing_unit ? [document.issuing_unit] : []);
  const tags = includeCurrentOptions(options?.tags, document?.tags ?? []);

  async function submit(values: DocumentFormValues) {
    if (pending.current) return;
    const changes = document ? documentUpdatePayload(values, document) : null;
    if (changes && !Object.keys(changes).length) { onClose(); return; }
    pending.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const result = document && changes ? await updateDocument(document.id, changes) : await createDocument(documentFormPayload(values));
      onSaved(result.data);
    } catch (cause) {
      if (isAxiosError(cause) && cause.response?.status === 409) {
        const message = "Mã văn bản đã tồn tại. Vui lòng nhập mã khác.";
        form.setFields([{ name: "code", errors: [message] }]);
        form.scrollToField("code", { focus: true });
        setError(message);
      } else {
        setError(isAxiosError(cause) && cause.response?.status === 401
          ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại." : requestError(cause));
      }
    } finally {
      pending.current = false;
      setSubmitting(false);
    }
  }

  return <Drawer title={document ? "Sửa thông tin văn bản" : "Tạo văn bản"} open size={680} onClose={() => { if (!pending.current) onClose(); }}
    closable={!submitting} keyboard={!submitting} mask={{ closable: !submitting }}
    footer={<div className={styles.footer}>
      <Button onClick={onClose} disabled={submitting}>Hủy</Button>
      <Button type="primary" icon={document ? <SaveOutlined /> : <PlusOutlined />} htmlType="submit" form={formId} loading={submitting}>{document ? "Lưu thay đổi" : "Tạo văn bản"}</Button>
    </div>}>
    {!document && <Alert className={styles.intro} type="info" showIcon title="Văn bản mới sẽ được lưu ở trạng thái Bản nháp." />}
    {error && <Alert role="alert" className={styles.error} type="error" showIcon title={error} />}
    {optionsError && <Alert className={styles.error} type="warning" showIcon title={document
      ? "Chưa tải được danh mục. Các lựa chọn hiện tại được giữ nguyên; bạn vẫn có thể sửa các thông tin khác."
      : "Chưa tải được danh mục. Bạn vẫn có thể tạo văn bản và bổ sung thông tin sau."}
      action={<Button onClick={reload} loading={loadingOptions}>Thử lại</Button>} />}
    <Form<DocumentFormValues> id={formId} form={form} layout="vertical" onFinish={submit} disabled={submitting}
      initialValues={documentInitialValues(document)} scrollToFirstError={{ focus: true }}
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
          options={types.map((item) => ({ value: item.id, label: item.is_active ? item.name : `${item.name} (Ngừng sử dụng)`, disabled: !item.is_active }))} notFoundContent="Chưa có loại văn bản" /></Form.Item>
        <Form.Item name="issuing_unit_id" label="Đơn vị ban hành"><Select allowClear showSearch optionFilterProp="label"
          loading={loadingOptions} disabled={submitting || !options} placeholder="Chọn đơn vị ban hành"
          options={units.map((item) => ({ value: item.id, label: item.is_active ? item.name : `${item.name} (Ngừng sử dụng)`, disabled: !item.is_active }))} notFoundContent="Chưa có đơn vị ban hành" /></Form.Item>
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
        options={tags.map((item) => ({ value: item.id, label: item.name }))} notFoundContent="Chưa có thẻ" /></Form.Item>
    </Form>
  </Drawer>;
}
