import axios from "axios";

const api = axios.create({ baseURL: "/api", timeout: 20000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 && typeof window !== "undefined" &&
      window.location.pathname !== "/login"
    ) {
      window.location.replace("/login?expired=1");
    }
    return Promise.reject(error);
  },
);

export default api;
