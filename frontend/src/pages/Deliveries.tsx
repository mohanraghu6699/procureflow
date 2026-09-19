import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listDeliveries } from "../api/endpoints";
import { Pagination } from "../components/Pagination";
import { StatusBadge, statusLabel } from "../components/StatusBadge";
import type { DeliveryStatus } from "../types";

const STATUSES: DeliveryStatus[] = ["IN_TRANSIT", "PARTIAL", "DELIVERED"];
const PAGE_SIZE = 10;

export function Deliveries() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["deliveries", status, page],
    queryFn: () => listDeliveries({ status: status || undefined, page, page_size: PAGE_SIZE }),
  });
  const items = query.data?.items;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Deliveries</h1>
          <p className="text-sm text-slate-500">Track and update delivery status for purchase orders</p>
        </div>
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
              {statusLabel(s)}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100 bg-slate-50">
              <th className="px-4 py-2.5 font-medium">Purchase Order</th>
              <th className="px-4 py-2.5 font-medium">Delivery Date</th>
              <th className="px-4 py-2.5 font-medium">Remarks</th>
              <th className="px-4 py-2.5 font-medium">Updated By</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {items?.map((d) => (
              <tr key={d.id} className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors">
                <td className="px-4 py-3">
                  <Link to={`/purchase-orders/${d.po_id}`} className="text-brand-600 font-medium">
                    {d.po_number ?? "View Order"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {d.delivery_date ? new Date(d.delivery_date).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-3 text-slate-600 max-w-xs truncate">{d.remarks || "—"}</td>
                <td className="px-4 py-3 text-slate-600">{d.updated_by_name}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={d.status} />
                </td>
              </tr>
            ))}
            {items?.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-slate-400">
                  No delivery records found
                </td>
              </tr>
            )}
          </tbody>
        </table></div>
        {query.data && <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPageChange={setPage} />}
      </div>
    </div>
  );
}
