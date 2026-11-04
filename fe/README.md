This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

python3.11 -m venv .venv
source .venv/bin/activate
uvicorn app.main:app --reload

#start celery
celery -A app.core.celery_app.celery_app worker -l info

## Đối chiếu trích xuất văn bản

Vào **Văn bản → Chi tiết → Phiên bản → Đối chiếu trích xuất** trên một phiên bản
PDF. Route: `/documents/{documentId}/versions/{versionId}/review`.

- Hai cột: PDF gốc và các kết quả trích xuất; chọn bằng chứng để chuyển trang.
- Đánh dấu chính xác đoạn trích trong bản text lưu cùng evidence. Chưa tô vùng
  trên ảnh PDF vì dữ liệu extraction chưa có tọa độ chữ.
- Lọc loại thông tin/trạng thái, phân trang, chọn lịch sử run, tạo/retry run.
- Duyệt, sửa và duyệt, từ chối; xem người duyệt và lịch sử thay đổi.
- Xử lý xung đột revision và retry HTTP bằng idempotency key; không giả lập lưu
  kết quả ở local state. Giá trị gốc và evidence vẫn giữ nguyên.

Yêu cầu Node **22.13+**, `npm install`, backend đã chạy `alembic upgrade head`
đến revision `c9a42e7d0b13`, Redis/Celery hoạt động để tạo run mới. Các PDF không
vượt quá giới hạn upload hiện tại (20 MB). DOCX chưa hỗ trợ màn hình PDF này.

React-PDF 11 được tải phía client; worker, CMaps, fonts và WASM được phục vụ tại
chính FE, không dùng CDN. `postinstall`, `predev`, `prebuild` sao chép tài nguyên
PDF.js vào `public/pdfjs/` (gitignored). Triển khai cần giữ thư mục `public/`.
Tham khảo [hướng dẫn chính thức React-PDF](https://github.com/wojtekmaj/react-pdf/tree/v11.0.0).

Route `/api/documents/{documentId}/versions/{versionId}/pdf` kiểm tra session,
xin URL mới từ API download có phân quyền, rồi stream PDF qua FE với `no-store`.
Chỉ nhận URL HTTPS của R2 (`*.r2.cloudflarestorage.com`), không theo redirect và
không chuyển JWT đến storage. Không cần CORS R2 cho viewer. Việc tải file thông
thường vẫn dùng luồng download hiện có. Custom domain storage chưa hỗ trợ ở
proxy PDF này.

Kiểm tra:

```bash
npm run lint
npm run typecheck
npm run build
npm run test:extraction-review
npm run test:documents
```

`tests/run-extraction-smoke.sh` tạo PostgreSQL tạm, chạy toàn bộ test BE rồi mở
FE/API thử nghiệm (localhost:3100 / 127.0.0.1:8001). Cần PostgreSQL 16 và hai file
PDF/page text trong `be/.cache/extraction-smoke/`. Dùng tài khoản thử nghiệm được
khai báo trong `tests/serve_backend.py`; không dùng tài khoản thật. R2 được thay
bằng file PDF cache qua `tests/helpers/mock-r2.mjs`, chỉ trong process thử nghiệm
với `EXTRACTION_REVIEW_SMOKE=1`. Ctrl-C dừng server và rollback schema thử nghiệm.

Kiểm tra lượt này: 273 test BE pass trên PostgreSQL tạm; 20 test mới của FE pass,
98 test FE có sẵn pass; build và lint pass. Kiểm thử tương tác trình duyệt chưa
hoàn tất vì quyền truy cập môi trường localhost không được cấp. Migration chưa
được áp dụng vào database hiện tại của dự án.
