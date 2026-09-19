import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDashboardSummary, fetchRecentActivity, listPurchaseRequests } from "../api/endpoints";
import { StatusBadge, statusLabel } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { describeTrend, formatCurrency, type TrendInfo } from "../utils/format";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#898781",
  SUBMITTED: "#2a78d6",
  APPROVED: "#0ca30c",
  REJECTED: "#d03b3b",
  COMPLETED: "#4a3aa7",
};

function formatRelativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(1, Math.round(diffMs / 60000));
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

const TREND_STYLE: Record<TrendInfo["tone"], { arrow: string; cls: string }> = {
  up: { arrow: "▲", cls: "text-emerald-600" },
  down: { arrow: "▼", cls: "text-red-600" },
  flat: { arrow: "–", cls: "text-slate-400" },
};

function StatCard({
  label,
  value,
  trend,
  accent,
}: {
  label: string;
  value: string;
  trend?: TrendInfo;
  accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs font-medium text-slate-500">{label}</div>
        <div className={`w-9 h-9 shrink-0 rounded-lg flex items-center justify-center text-white ${accent}`}>◆</div>
      </div>
      <div className="text-2xl font-semibold text-slate-900 mt-1 whitespace-nowrap">{value}</div>
      <div className={`text-xs mt-2 flex items-center gap-1 min-h-[1rem] ${trend ? TREND_STYLE[trend.tone].cls : ""}`}>
        {trend && (
          <>
            <span aria-hidden>{TREND_STYLE[trend.tone].arrow}</span>
            {trend.text}
          </>
        )}
      </div>
    </div>
  );
}

export function Dashboard() {
  const { user } = useAuth();
  const canApprove = user?.role === "APPROVER" || user?.role === "ADMIN";

  const summaryQuery = useQuery({ queryKey: ["dashboard-summary"], queryFn: fetchDashboardSummary });
  const activityQuery = useQuery({ queryKey: ["dashboard-activity"], queryFn: fetchRecentActivity });
  const recentPRsQuery = useQuery({
    queryKey: ["recent-prs"],
    queryFn: () => listPurchaseRequests({ page: 1, page_size: 5, sort_by: "created_at", sort_dir: "desc" }),
  });
  const pendingApprovalsQuery = useQuery({
    queryKey: ["pending-approvals-widget"],
    queryFn: () => listPurchaseRequests({ status: "SUBMITTED", page: 1, page_size: 4 }),
    enabled: canApprove,
  });

  const summary = summaryQuery.data;
  const trends = summary?.trends;
  const total = summary ? summary.pr_by_status.reduce((n, s) => n + s.count, 0) : 0;
  const pieData = summary && total > 0 ? summary.pr_by_status : [{ status: "NONE", count: 1 }];

  const chartRowCols = canApprove
    ? "grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_minmax(0,1fr)] gap-4"
    : "grid grid-cols-1 lg:grid-cols-3 gap-4";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Overview of your purchase-to-pay activities</p>
        </div>
        <div className="text-sm text-slate-500 bg-white border border-slate-200 rounded-lg px-3 py-2">
          {new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5 gap-4">
        <StatCard
          label="Total Purchase Requests"
          value={String(summary?.total_purchase_requests ?? "—")}
          trend={trends && describeTrend(trends.prs_created_month, "month", "created")}
          accent="bg-blue-500"
        />
        <StatCard
          label="Pending Approval"
          value={String(summary?.pending_approval ?? "—")}
          trend={trends && describeTrend(trends.submitted_week, "week", "submitted")}
          accent="bg-amber-500"
        />
        <StatCard
          label="Total Purchase Orders"
          value={String(summary?.total_purchase_orders ?? "—")}
          trend={trends && describeTrend(trends.pos_created_month, "month", "created")}
          accent="bg-emerald-500"
        />
        <StatCard
          label="Pending Delivery"
          value={String(summary?.pending_delivery ?? "—")}
          trend={trends && describeTrend(trends.ordered_week, "week", "ordered")}
          accent="bg-violet-500"
        />
        <StatCard
          label="Total Spend (Approved)"
          value={summary ? `AED ${formatCurrency(summary.total_spend_approved)}` : "—"}
          trend={trends && describeTrend(trends.approved_spend_month, "month", "approved", true)}
          accent="bg-slate-700"
        />
      </div>

      <div className={chartRowCols}>
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="text-sm font-semibold text-slate-800 mb-3">Purchase Requests by Status</div>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <div className="relative w-44 h-44 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="count"
                    nameKey="status"
                    cx="50%"
                    cy="50%"
                    innerRadius={56}
                    outerRadius={80}
                    paddingAngle={total > 0 ? 2 : 0}
                    isAnimationActive={false}
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.status} fill={STATUS_COLORS[entry.status] ?? "#e5e7eb"} stroke="#fff" strokeWidth={2} />
                    ))}
                  </Pie>
                  {total > 0 && (
                    <Tooltip formatter={(value: number, _name, item) => [value, statusLabel(item.payload.status)]} />
                  )}
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="text-2xl font-semibold text-slate-900 leading-none">{total}</div>
                <div className="text-xs text-slate-400 mt-1">Total</div>
              </div>
            </div>
            <div className="space-y-1.5 min-w-[9rem] flex-1">
              {summary?.pr_by_status.map((s) => {
                const pct = total > 0 ? Math.round((s.count / total) * 100) : 0;
                return (
                  <div key={s.status} className="flex items-center gap-2 text-xs text-slate-600">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: STATUS_COLORS[s.status] }} />
                    <span className="truncate">{statusLabel(s.status)}</span>
                    <span className="ml-auto font-medium text-slate-800 whitespace-nowrap">
                      {s.count} <span className="font-normal text-slate-400">({pct}%)</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className={`bg-white rounded-xl border border-slate-200 p-4 ${canApprove ? "lg:col-span-2 xl:col-span-1" : "lg:col-span-2"}`}>
          <div className="text-sm font-semibold text-slate-800 mb-3">Monthly Trend — PRs vs POs</div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={summary?.monthly_trend || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: "#898781" }} axisLine={{ stroke: "#c3c2b7" }} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "#898781" }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip itemSorter={(item) => (item.dataKey === "pr_count" ? 0 : 1)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="pr_count" name="PRs" fill="#2a78d6" radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar dataKey="po_count" name="POs" fill="#eb6834" radius={[4, 4, 0, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {canApprove && (
          <div className="bg-white rounded-xl border border-slate-200 lg:col-span-3 xl:col-span-1">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
              <div className="text-sm font-semibold text-slate-800">Pending Approvals</div>
              <Link to="/approvals" className="text-xs text-brand-600 font-medium">
                View All
              </Link>
            </div>
            <div className="divide-y divide-slate-100">
              {pendingApprovalsQuery.data?.items.map((pr) => (
                <Link
                  key={pr.id}
                  to={`/purchase-requests/${pr.id}`}
                  className="block px-4 py-3 hover:bg-brand-50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-slate-800">{pr.pr_number}</span>
                    <span className="text-sm font-semibold text-slate-700 whitespace-nowrap">
                      {pr.currency} {formatCurrency(pr.amount)}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 truncate mt-0.5">{pr.description}</div>
                  <div className="flex items-center justify-between gap-3 text-xs text-slate-400 mt-0.5">
                    <span className="truncate">Requested by {pr.requester_name}</span>
                    <span className="whitespace-nowrap">{formatRelativeTime(pr.updated_at)}</span>
                  </div>
                </Link>
              ))}
              {pendingApprovalsQuery.data?.items.length === 0 && (
                <div className="px-4 py-8 text-sm text-slate-400 text-center">No pending approvals</div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 lg:col-span-2">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <div className="text-sm font-semibold text-slate-800">Recent Purchase Requests</div>
            <Link to="/purchase-requests" className="text-xs text-brand-600 font-medium">
              View All
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                  <th className="px-4 py-2 font-medium">PR Number</th>
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 font-medium">Description</th>
                  <th className="px-4 py-2 font-medium">Department</th>
                  <th className="px-4 py-2 font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentPRsQuery.data?.items.map((pr) => (
                  <tr key={pr.id} className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors">
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <Link to={`/purchase-requests/${pr.id}`} className="text-brand-600 font-medium">
                        {pr.pr_number}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 whitespace-nowrap">
                      {new Date(pr.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 max-w-[16rem] truncate" title={pr.description}>
                      {pr.description}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 whitespace-nowrap">{pr.department_name}</td>
                    <td className="px-4 py-2.5 text-slate-700 whitespace-nowrap">
                      {pr.currency} {formatCurrency(pr.amount)}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <StatusBadge status={pr.status} />
                    </td>
                  </tr>
                ))}
                {recentPRsQuery.data?.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-400">
                      No purchase requests yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200">
          <div className="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">Recent Activity</div>
          <div className="p-4 space-y-3">
            {activityQuery.data?.map((item) => (
              <div key={item.id} className="flex items-start gap-2.5 text-sm">
                <span className="w-2 h-2 rounded-full bg-brand-500 mt-1.5 shrink-0" />
                <div>
                  <div className="text-slate-700">{item.message}</div>
                  <div className="text-xs text-slate-400">{formatRelativeTime(item.timestamp)}</div>
                </div>
              </div>
            ))}
            {activityQuery.data?.length === 0 && <div className="text-sm text-slate-400">No recent activity</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
