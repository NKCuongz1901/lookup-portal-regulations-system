export interface PaginationMeta {
  page: number;
  itemsPerPage: number;
  total: number;
  totalPages: number;
}

export interface ApiResponse<T> {
  message: string;
  status_code: number;
  data: T;
  meta: PaginationMeta | null;
}

export interface ListParams {
  page?: number;
  itemsPerPage?: number;
  search?: string;
}
