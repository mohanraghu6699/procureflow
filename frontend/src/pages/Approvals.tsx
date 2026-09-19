import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { approvePurchaseRequest, listPurchaseRequests, rejectPurchaseRequest } from "../api/endpoints";
import { getErrorMessage } from "../api/client";
import { Pagination } from "../components/Pagination";
import { useAuth } from "../context/AuthContext";
import { formatCurrency } from "../utils/format";


export function Approvals() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const pageSize = 10;

  const query = useQuery({
    queryKey: ["approvals", page],
    queryFn: () => listPurchaseRequests({ status: "SUBMITTED", page, page_size: pageSize, sort_by: "created_at", sort_dir: "asc" }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({ queryKey: ["purchase-requests"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const approveMutation = useMutation({
    mutationFn: (id: string) => approvePurchaseRequest(id),
    onSuccess: invalidate,
    onError: (err) => setError(getErrorMessage(err)),
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectPurchaseRequest(id),
    onSuccess: invalidate,
    onError: (err) => setError(getErrorMessage(err)),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Approvals</h1>
        <p className="text-sm text-slate-500">Purchase requests awaiting your decision</p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100 bg-slate-50">
              <th className="px-4 py-2.5 font-medium">PR Number</th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Requester</th>
              <th className="px-4 py-2.5 font-medium">Amount</th>
              <th className="px-4 py-2.5 font-medium">Required Date</th>
              <th className="px-4 py-2.5 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {query.data?.items.map((pr) => {
              const isSelf = pr.requester_id === user?.id;
              return (
                <tr key={pr.id} className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/purchase-requests/${pr.id}`} className="text-brand-600 font-medium">
                      {pr.pr_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-600 max-w-xs truncate">{pr.description}</td>
                  <td className="px-4 py-3 text-slate-600">{pr.requester_name}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {pr.currency} {formatCurrency(pr.amount)}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{new Date(pr.required_date).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    {isSelf ? (
                      <span className="text-xs text-slate-400 float-right">Self-requested</span>
                    ) : (
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => approveMutation.mutate(pr.id)}
                          disabled={approveMutation.isPending}
                          className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded-md px-3 py-1.5 disabled:opacity-60"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => rejectMutation.mutate(pr.id)}
                          disabled={rejectMutation.isPending}
                          className="text-xs bg-red-600 hover:bg-red-700 text-white rounded-md px-3 py-1.5 disabled:opacity-60"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {query.data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-400">
                  No purchase requests pending approval
                </td>
              </tr>
            )}
          </tbody>
        </table></div>
        {query.data && <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />}
      </div>
    </div>
  );
}
