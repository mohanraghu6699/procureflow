export type UserRole = "REQUESTER" | "APPROVER" | "ADMIN";

export type PRStatus = "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "COMPLETED";
export type POStatus = "OPEN" | "IN_TRANSIT" | "PARTIALLY_DELIVERED" | "DELIVERED" | "COMPLETED";
export type DeliveryStatus = "PENDING" | "IN_TRANSIT" | "PARTIAL" | "DELIVERED";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department_id?: string | null;
  department_name?: string | null;
}

export interface Department {
  id: string;
  name: string;
  is_active: boolean;
}

export interface Category {
  id: string;
  name: string;
  is_active: boolean;
}

export interface Vendor {
  id: string;
  name: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  address?: string | null;
  is_active: boolean;
  category_ids: string[];
}

export interface PurchaseRequest {
  id: string;
  pr_number: string;
  requester_id: string;
  requester_name?: string | null;
  department_id: string;
  department_name?: string | null;
  description: string;
  category_id: string;
  category_name?: string | null;
  amount: string;
  currency: string;
  required_date: string;
  vendor_id?: string | null;
  vendor_name?: string | null;
  status: PRStatus;
  created_at: string;
  updated_at: string;
}

export interface PRStatusHistoryItem {
  id: string;
  from_status?: PRStatus | null;
  to_status: PRStatus;
  changed_by_id: string;
  changed_by_name?: string | null;
  comment?: string | null;
  changed_at: string;
}

export interface PurchaseRequestDetail extends PurchaseRequest {
  status_history: PRStatusHistoryItem[];
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  pr_id: string;
  pr_number?: string | null;
  vendor_id: string;
  vendor_name?: string | null;
  amount: string;
  currency: string;
  status: POStatus;
  required_date: string;
  created_by_id: string;
  created_by_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Delivery {
  id: string;
  po_id: string;
  po_number?: string | null;
  delivery_date?: string | null;
  status: DeliveryStatus;
  remarks?: string | null;
  updated_by_id: string;
  updated_by_name?: string | null;
  updated_at: string;
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  deliveries: Delivery[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardSummary {
  total_purchase_requests: number;
  pending_approval: number;
  total_purchase_orders: number;
  pending_delivery: number;
  total_spend_approved: string;
  pr_by_status: { status: string; count: number }[];
  po_by_status: { status: string; count: number }[];
  monthly_trend: { month: string; pr_count: number; po_count: number }[];
  trends: DashboardTrends;
}

export interface RecentActivityItem {
  id: string;
  type: string;
  message: string;
  timestamp: string;
}

export interface TrendPoint {
  current: string;
  previous: string;
}

export interface DashboardTrends {
  prs_created_month: TrendPoint;
  pos_created_month: TrendPoint;
  submitted_week: TrendPoint;
  ordered_week: TrendPoint;
  approved_spend_month: TrendPoint;
}
