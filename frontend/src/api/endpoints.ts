import { apiClient } from "./client";
import type {
  Category,
  DashboardSummary,
  Delivery,
  Department,
  Paginated,
  PurchaseOrder,
  PurchaseOrderDetail,
  PurchaseRequest,
  PurchaseRequestDetail,
  RecentActivityItem,
  User,
  UserRole,
  Vendor,
} from "../types";

// ---------- Auth ----------

export async function login(email: string, password: string) {
  const { data } = await apiClient.post<{ access_token: string; user: User }>("/api/auth/login", {
    email,
    password,
  });
  return data;
}

export async function fetchMe() {
  const { data } = await apiClient.get<User>("/api/auth/me");
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  await apiClient.post("/api/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

// ---------- Master data ----------

export async function fetchDepartments(includeInactive = false) {
  const { data } = await apiClient.get<Department[]>("/api/master-data/departments", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function fetchCategories(includeInactive = false) {
  const { data } = await apiClient.get<Category[]>("/api/master-data/categories", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function fetchVendors(includeInactive = false, categoryId?: string) {
  const { data } = await apiClient.get<Vendor[]>("/api/master-data/vendors", {
    params: { include_inactive: includeInactive, category_id: categoryId },
  });
  return data;
}

export async function createDepartment(name: string) {
  const { data } = await apiClient.post<Department>("/api/master-data/departments", { name });
  return data;
}

export async function createCategory(name: string) {
  const { data } = await apiClient.post<Category>("/api/master-data/categories", { name });
  return data;
}

export async function createVendor(payload: { name: string; category_ids: string[] }) {
  const { data } = await apiClient.post<Vendor>("/api/master-data/vendors", payload);
  return data;
}

export async function updateVendorCategories(id: string, categoryIds: string[]) {
  const { data } = await apiClient.put<Vendor>(`/api/master-data/vendors/${id}/categories`, {
    category_ids: categoryIds,
  });
  return data;
}

export async function deleteDepartment(id: string) {
  await apiClient.delete(`/api/master-data/departments/${id}`);
}

export async function deleteCategory(id: string) {
  await apiClient.delete(`/api/master-data/categories/${id}`);
}

export async function deleteVendor(id: string) {
  await apiClient.delete(`/api/master-data/vendors/${id}`);
}

export async function reactivateDepartment(id: string) {
  const { data } = await apiClient.post<Department>(`/api/master-data/departments/${id}/reactivate`);
  return data;
}

export async function reactivateCategory(id: string) {
  const { data } = await apiClient.post<Category>(`/api/master-data/categories/${id}/reactivate`);
  return data;
}

export async function reactivateVendor(id: string) {
  const { data } = await apiClient.post<Vendor>(`/api/master-data/vendors/${id}/reactivate`);
  return data;
}

// ---------- Users ----------

export async function listUsers() {
  const { data } = await apiClient.get<User[]>("/api/auth/users");
  return data;
}

export interface UserCreatePayload {
  name: string;
  email: string;
  password: string;
  role: UserRole;
  department_id?: string | null;
}

export async function createUser(payload: UserCreatePayload) {
  const { data } = await apiClient.post<User>("/api/auth/users", payload);
  return data;
}

// ---------- Purchase Requests ----------

export interface PRListParams {
  status?: string;
  department_id?: string;
  category_id?: string;
  search?: string;
  mine?: boolean;
  awaiting_po?: boolean;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export async function listPurchaseRequests(params: PRListParams) {
  const { data } = await apiClient.get<Paginated<PurchaseRequest>>("/api/purchase-requests", { params });
  return data;
}

export async function getPurchaseRequest(id: string) {
  const { data } = await apiClient.get<PurchaseRequestDetail>(`/api/purchase-requests/${id}`);
  return data;
}

export interface PRPayload {
  department_id: string;
  description: string;
  category_id: string;
  amount: number;
  currency: string;
  required_date: string;
  vendor_id?: string | null;
}

export async function createPurchaseRequest(payload: PRPayload) {
  const { data } = await apiClient.post<PurchaseRequest>("/api/purchase-requests", payload);
  return data;
}

export async function updatePurchaseRequest(id: string, payload: Partial<PRPayload>) {
  const { data } = await apiClient.put<PurchaseRequest>(`/api/purchase-requests/${id}`, payload);
  return data;
}

export async function submitPurchaseRequest(id: string) {
  const { data } = await apiClient.post<PurchaseRequest>(`/api/purchase-requests/${id}/submit`);
  return data;
}

export async function approvePurchaseRequest(id: string, comment?: string) {
  const { data } = await apiClient.post<PurchaseRequest>(`/api/purchase-requests/${id}/approve`, { comment });
  return data;
}

export async function rejectPurchaseRequest(id: string, comment?: string) {
  const { data } = await apiClient.post<PurchaseRequest>(`/api/purchase-requests/${id}/reject`, { comment });
  return data;
}

export async function deletePurchaseRequest(id: string) {
  await apiClient.delete(`/api/purchase-requests/${id}`);
}

// ---------- Purchase Orders ----------

export interface POListParams {
  status?: string;
  vendor_id?: string;
  search?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export async function listPurchaseOrders(params: POListParams) {
  const { data } = await apiClient.get<Paginated<PurchaseOrder>>("/api/purchase-orders", { params });
  return data;
}

export async function getPurchaseOrder(id: string) {
  const { data } = await apiClient.get<PurchaseOrderDetail>(`/api/purchase-orders/${id}`);
  return data;
}

export async function createPurchaseOrder(payload: { pr_id: string; vendor_id: string; amount: number }) {
  const { data } = await apiClient.post<PurchaseOrder>("/api/purchase-orders", payload);
  return data;
}

// ---------- Deliveries ----------

export async function recordDelivery(
  poId: string,
  payload: { delivery_date?: string | null; status: string; remarks?: string }
) {
  const { data } = await apiClient.post<PurchaseOrder>(`/api/purchase-orders/${poId}/deliveries`, payload);
  return data;
}

export async function listDeliveries(status?: string) {
  const { data } = await apiClient.get<Delivery[]>("/api/deliveries", { params: { status } });
  return data;
}

// ---------- Dashboard ----------

export async function fetchDashboardSummary() {
  const { data } = await apiClient.get<DashboardSummary>("/api/dashboard/summary");
  return data;
}

export async function fetchRecentActivity() {
  const { data } = await apiClient.get<RecentActivityItem[]>("/api/dashboard/recent-activity");
  return data;
}
