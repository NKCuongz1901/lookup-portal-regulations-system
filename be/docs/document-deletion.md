# Xóa văn bản

`DELETE /api/v1/documents/{document_id}` dành cho ADMIN và STAFF. API trả HTTP 200 với `data: null` khi thành công; ID không tồn tại hoặc đã xóa trả 404.

Đây là **xóa mềm**: ghi `deleted_at`, `deleted_by` và thông tin cập nhật. Bản ghi, file R2, phiên bản, nội dung đã phân tích, thẻ và liên kết được giữ lại. Mã văn bản vẫn được giữ chỗ và không được dùng lại khi tạo văn bản mới.

Văn bản đã xóa không xuất hiện trong danh sách hoặc tổng số kết quả, kể cả khi lọc theo trạng thái Lưu trữ. Các API chi tiết, sửa, lưu trữ, danh sách phiên bản, upload và tạo link download đều trả 404. Link download đã cấp trước đó vẫn dùng được đến khi hết hạn. Hiện chưa có API khôi phục hoặc xóa vĩnh viễn.

Trước khi chạy BE với thay đổi này, áp dụng migration trong thư mục `be`:

```sh
.venv/bin/alembic upgrade head
```

Migration `a4d90b2c7e61` thêm hai cột nullable, khóa ngoại người xóa và index. Văn bản hiện có mặc định chưa bị xóa. Không downgrade migration này khi còn cần giữ trạng thái xóa, vì việc bỏ cột sẽ làm mất dấu xóa.

FE gọi API qua `/api/backend/documents/{id}` bằng session HttpOnly, có kiểm tra origin. Nút thùng rác nằm ở cột Thao tác, mở hộp xác nhận trước khi gọi API. Khi thành công, danh sách được tải lại từ trang đầu; phản hồi 404 cũng làm mới danh sách để loại bỏ dòng đã bị xóa từ phiên khác.

Kiểm thử PostgreSQL nằm trong `tests/postgres/test_document_delete_api.py`; mỗi test dùng schema tạm và rollback. Các lời gọi kho lưu trữ được mock, không xóa file R2 thật.
