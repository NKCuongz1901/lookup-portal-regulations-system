export const formatNumber = (value: number) => new Intl.NumberFormat("vi-VN").format(value);
export const formatDate = (value: string | null) => value
  ? new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value))
  : "Chưa thiết lập";
export const initials = (name: string) => name.trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase();
