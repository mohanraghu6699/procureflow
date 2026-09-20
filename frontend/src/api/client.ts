import axios from "axios";

// No fallback on purpose: the API address comes from the environment only (frontend/.env, or a build
// argument in Docker and Cloud Build). vite.config.ts refuses to start or build without it.
const apiBaseUrl: string | undefined = import.meta.env.VITE_API_BASE_URL;
if (!apiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not set. Add it to frontend/.env (see .env.example).");
}
export const API_BASE_URL: string = apiBaseUrl;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

interface ValidationDetail {
  loc?: (string | number)[];
  msg: string;
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data?.detail) {
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.errors)) {
        return (data.errors as ValidationDetail[]).map((e) => `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(", ");
      }
    }
    return error.message;
  }
  return "Something went wrong";
}
