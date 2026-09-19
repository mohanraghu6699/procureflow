import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchCategories, fetchDepartments, listPurchaseRequests } from "../../api/endpoints";
import { Pagination } from "../../components/Pagination";
import { StatusBadge } from "../../components/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import type { PRStatus } from "../../types";
import { formatCurrency } from "../../utils/format";

const STATUSES: PRStatus[] = ["DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "COMPLETED"];


export function PRList() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: () => fetchDepartments() });
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: () => fetchCategories() });

  const prQuery = useQuery({
    queryKey: ["purchase-requests", { search, status, departmentId, categoryId, sortBy, sortDir, page }],
    queryFn: () =>
      listPurchaseRequests({
        search: search || undefined,
        status: status || undefined,
        department_id: departmentId || undefined,
        category_id: categoryId || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        page_size: pageSize,
      }),
  });

  function toggleSort(column: string) {
    if (sortBy === column) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortDir("desc");
    }
    setPage(1);
  }

  const canCreate = user?.role === "REQUESTER" || user?.role === "ADMIN";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Purchase Requests</h1>
          <p className="text-sm text-slate-500">Create, track, and manage purchase requests</p>
        </div>
        {canCreate && (
          <button
            onClick={() => navigate("/purchase-requests/new")}
            className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-4 py-2.5"
          >
            + New Purchase Request
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap gap-3 items-center">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search PR number or description..."
          className="flex-1 min-w-[200px] rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={departmentId}
          onChange={(e) => {
            setDepartmentId(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Departments</option>
          {departmentsQuery.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select
          value={categoryId}
          onChange={(e) => {
            setCategoryId(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Categories</option>
          {categoriesQuery.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100 bg-slate-50">
              <th className="px-4 py-2.5 font-medium cursor-pointer" onClick={() => toggleSort("pr_number")}>
                PR Number {sortBy === "pr_number" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Department</th>
              <th className="px-4 py-2.5 font-medium cursor-pointer" onClick={() => toggleSort("amount")}>
                Amount {sortBy === "amount" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="px-4 py-2.5 font-medium cursor-pointer" onClick={() => toggleSort("required_date")}>
                Required Date {sortBy === "required_date" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {prQuery.data?.items.map((pr) => (
              <tr
                key={pr.id}
                className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors cursor-pointer"
                onClick={() => navigate(`/purchase-requests/${pr.id}`)}
              >
                <td className="px-4 py-3">
                  <Link to={`/purchase-requests/${pr.id}`} className="text-brand-600 font-medium" onClick={(e) => e.stopPropagation()}>
                    {pr.pr_number}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600 max-w-xs truncate">{pr.description}</td>
                <td className="px-4 py-3 text-slate-600">{pr.department_name}</td>
                <td className="px-4 py-3 text-slate-700">
                  {pr.currency} {formatCurrency(pr.amount)}
                </td>
                <td className="px-4 py-3 text-slate-600">{new Date(pr.required_date).toLocaleDateString()}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={pr.status} />
                </td>
              </tr>
            ))}
            {prQuery.data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-400">
                  No purchase requests found
                </td>
              </tr>
            )}
          </tbody>
        </table></div>
        {prQuery.data && (
          <Pagination page={page} pageSize={pageSize} total={prQuery.data.total} onPageChange={setPage} />
        )}
      </div>
    </div>
  );
}
