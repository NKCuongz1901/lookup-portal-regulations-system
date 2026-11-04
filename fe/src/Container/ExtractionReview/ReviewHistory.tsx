"use client";
import { useCallback, useState } from "react";
import { Alert, Button, Empty, Pagination, Skeleton, Tag } from "antd";
import { getFieldReviews } from "@/apis/extractionApis";
import useResource from "@/hooks/useResource";
import styles from "./ExtractionReview.module.scss";

export default function ReviewHistory({ fieldId }: { fieldId: number }) {
  const [page, setPage] = useState(1);
  const loader = useCallback((signal: AbortSignal) => getFieldReviews(fieldId, page, signal), [fieldId, page]);
  const { data, loading, error, reload } = useResource(loader);
  return <div className={styles.history}>
    {loading ? <Skeleton active paragraph={{ rows: 2 }} /> : error ? <Alert type="error" title={error} action={<Button onClick={reload}>Thử lại</Button>} />
      : data?.data.length ? <>
        <ol>{data.data.map((review) => <li key={review.id}>
          <div><Tag color={review.action === "reject" ? "red" : "green"}>{review.action === "approve" ? "Duyệt" : review.action === "correct" ? "Sửa và duyệt" : "Từ chối"}</Tag><b>{review.reviewer_name}</b></div>
          <time>{new Date(review.created_at).toLocaleString("vi-VN")}</time>
          {review.action === "correct" && <div className={styles.reviewChange}><del>{review.previous_value}</del><p>{review.new_value}</p></div>}
          {review.note && <p>{review.note}</p>}
        </li>)}</ol>
        <Pagination size="small" current={page} pageSize={5} total={data.meta?.total ?? 0} onChange={setPage} hideOnSinglePage showSizeChanger={false} />
      </> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có thao tác duyệt" />}
  </div>;
}
