import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchVendors, listPurchaseOrders } from "../../api/endpoints";
import { Pagination } from "../../components/Pagination";
import { StatusBadge } from "../../components/StatusBadge";
import type { POStatus } from "../../types";
import { formatCurrency, openOrderDue } from "../../utils/format";

const STATUSES: POStatus[] = ["OPEN", "IN_TRANSIT", "PARTIALLY_DELIVERED", "DELIVERED", "COMPLETED"];


export function POList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const vendorsQuery = useQuery({ queryKey: ["vendors"], queryFn: () => fetchVendors() });
  const poQuery = useQuery({
    queryKey: ["purchase-orders", { search, status, vendorId, page }],
    queryFn: () =>
      listPurchaseOrders({
        search: search || undefined,
        status: status || undefined,
        vendor_id: vendorId || undefined,
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_dir: "desc",
      }),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Purchase Orders</h1>
        <p className="text-sm text-slate-500">Track purchase orders issued against approved requests</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap gap-3 items-center">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search PO or PR number..."
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
          value={vendorId}
          onChange={(e) => {
            setVendorId(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Vendors</option>
          {vendorsQuery.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100 bg-slate-50">
              <th className="px-4 py-2.5 font-medium">PO Number</th>
              <th className="px-4 py-2.5 font-medium">Linked PR</th>
              <th className="px-4 py-2.5 font-medium">Vendor</th>
              <th className="px-4 py-2.5 font-medium">Amount</th>
              <th className="px-4 py-2.5 font-medium">Required By</th>
              <th className="px-4 py-2.5 font-medium">Created</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {poQuery.data?.items.map((po) => (
              <tr
                key={po.id}
                className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors cursor-pointer"
                onClick={() => navigate(`/purchase-orders/${po.id}`)}
              >
                <td className="px-4 py-3">
                  <Link to={`/purchase-orders/${po.id}`} className="text-brand-600 font-medium" onClick={(e) => e.stopPropagation()}>
                    {po.po_number}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600">{po.pr_number}</td>
                <td className="px-4 py-3 text-slate-600">{po.vendor_name}</td>
                <td className="px-4 py-3 text-slate-700 whitespace-nowrap">
                  {po.currency} {formatCurrency(po.amount)}
                </td>
                <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                  {new Date(po.required_date).toLocaleDateString()}
                  {po.status !== "COMPLETED" && openOrderDue(po.required_date).tone === "bad" && (
                    <span className="ml-2 text-xs font-medium text-red-600">Overdue</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">{new Date(po.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={po.status} />
                </td>
              </tr>
            ))}
            {poQuery.data?.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-400">
                  No purchase orders found
                </td>
              </tr>
            )}
          </tbody>
        </table></div>
        {poQuery.data && <Pagination page={page} pageSize={pageSize} total={poQuery.data.total} onPageChange={setPage} />}
      </div>
    </div>
  );
}
