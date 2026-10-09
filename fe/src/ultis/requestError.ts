import { isAxiosError } from "axios";

export function requestError(error: unknown): string {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 401) return "Email hoặc mật khẩu chưa chính xác. Vui lòng thử lại.";
    if (status === 403) return "Tài khoản này không có quyền truy cập trang quản trị. Vui lòng sử dụng tài khoản Admin hoặc Staff.";
    if (!status || status >= 500) return "Không thể kết nối hệ thống. Vui lòng thử lại sau ít phút.";
    if (status === 404) return "Không tìm thấy dữ liệu bạn yêu cầu.";
    if (status === 422) return "Thông tin chưa hợp lệ. Vui lòng kiểm tra và thử lại.";
    return "Không thể hoàn tất yêu cầu. Vui lòng thử lại.";
  }
  return "Đã có lỗi xảy ra. Vui lòng thử lại.";
}
