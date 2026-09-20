import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  approvePurchaseRequest,
  deletePurchaseRequest,
  getPurchaseRequest,
  listPurchaseOrders,
  rejectPurchaseRequest,
  submitPurchaseRequest,
} from "../../api/endpoints";
import { getErrorMessage } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { formatCurrency } from "../../utils/format";


export function PRDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const prQuery = useQuery({ queryKey: ["purchase-request", id], queryFn: () => getPurchaseRequest(id as string) });
  const poQuery = useQuery({
    queryKey: ["po-for-pr", prQuery.data?.pr_number],
    queryFn: () => listPurchaseOrders({ search: prQuery.data!.pr_number, page: 1, page_size: 5 }),
    enabled: Boolean(prQuery.data),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["purchase-request", id] });
    queryClient.invalidateQueries({ queryKey: ["purchase-requests"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const submitMutation = useMutation({
    mutationFn: () => submitPurchaseRequest(id as string),
    onSuccess: invalidate,
    onError: (err) => setError(getErrorMessage(err)),
  });
  const approveMutation = useMutation({
    mutationFn: () => approvePurchaseRequest(id as string, comment || undefined),
    onSuccess: () => {
      setComment("");
      invalidate();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectPurchaseRequest(id as string, comment.trim()),
    onSuccess: () => {
      setComment("");
      invalidate();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });
  const deleteMutation = useMutation({
    mutationFn: () => deletePurchaseRequest(id as string),
    onSuccess: () => navigate("/purchase-requests"),
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (prQuery.isLoading || !prQuery.data) {
    return <div className="text-sm text-slate-500">Loading...</div>;
  }

  const pr = prQuery.data;
  const rejection = [...pr.status_history].reverse().find((h) => h.to_status === "REJECTED");
  const isOwner = pr.requester_id === user?.id;
  const canEdit = (isOwner || user?.role === "ADMIN") && ["DRAFT", "REJECTED"].includes(pr.status);
  const canApproveReject =
    (user?.role === "APPROVER" || user?.role === "ADMIN") && pr.status === "SUBMITTED" && pr.requester_id !== user?.id;
  const canCreatePO =
    (user?.role === "APPROVER" || user?.role === "ADMIN") &&
    pr.status === "APPROVED" &&
    // A cancelled order does not count: the PR is waiting for a replacement.
    (poQuery.data?.items.filter((po) => po.status !== "CANCELLED").length ?? 0) === 0;

  return (
    <div className="space-y-4">
      <BackLink to="/purchase-requests" label="Purchase Requests" />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-900">{pr.pr_number}</h1>
            <StatusBadge status={pr.status} />
          </div>
          <p className="text-sm text-slate-500 mt-1 break-words">{pr.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0 whitespace-nowrap">
          {canEdit && (
            <button
              onClick={() => navigate(`/purchase-requests/${pr.id}/edit`)}
              className="text-sm border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-100 transition-colors"
            >
              Edit
            </button>
          )}
          {canEdit && (
            <button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending || (pr.status === "REJECTED" && pr.revision_required)}
              title={
                pr.status === "REJECTED" && pr.revision_required
                  ? "Edit the request to address the rejection first"
                  : undefined
              }
              className="text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-3 py-2 disabled:opacity-60"
            >
              Submit for Approval
            </button>
          )}
          {canEdit && pr.status === "DRAFT" && (isOwner || user?.role === "ADMIN") && (
            <button
              onClick={() => setConfirmDeleteOpen(true)}
              className="text-sm text-red-600 border border-red-200 rounded-lg px-3 py-2 hover:bg-red-50"
            >
              Delete
            </button>
          )}
          {canCreatePO && (
            <button
              onClick={() => navigate(`/purchase-orders/new?prId=${pr.id}`)}
              className="text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-3 py-2"
            >
              Create Purchase Order
            </button>
          )}
        </div>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

      {pr.status === "REJECTED" && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm">
          <div className="font-medium text-red-700">
            Rejected{rejection?.changed_by_name ? ` by ${rejection.changed_by_name}` : ""}
          </div>
          {rejection?.comment && <div className="text-red-600 mt-0.5 break-words">{rejection.comment}</div>}
          {pr.revision_required && (
            <div className="text-xs text-red-500 mt-1">
              Edit the request to address this before you can resubmit it.
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-sm font-semibold text-slate-800 mb-4">Request Details</div>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-y-4 text-sm">
            <div>
              <dt className="text-slate-400">Requester</dt>
              <dd className="text-slate-800 font-medium">{pr.requester_name}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Department</dt>
              <dd className="text-slate-800 font-medium">{pr.department_name}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Category</dt>
              <dd className="text-slate-800 font-medium">{pr.category_name}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Amount</dt>
              <dd className="text-slate-800 font-medium">
                {pr.currency} {formatCurrency(pr.amount)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Required Date</dt>
              <dd className="text-slate-800 font-medium">{new Date(pr.required_date).toLocaleDateString()}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Preferred Vendor</dt>
              <dd className="text-slate-800 font-medium">{pr.vendor_name || "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Created</dt>
              <dd className="text-slate-800 font-medium">{new Date(pr.created_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Last Updated</dt>
              <dd className="text-slate-800 font-medium">{new Date(pr.updated_at).toLocaleString()}</dd>
            </div>
          </dl>

          {poQuery.data && poQuery.data.items.length > 0 && (
            <div className="mt-5 pt-5 border-t border-slate-100">
              <div className="text-sm font-semibold text-slate-800 mb-2">Linked Purchase Orders</div>
              {poQuery.data.items.map((po) => (
                <Link
                  key={po.id}
                  to={`/purchase-orders/${po.id}`}
                  className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2.5 hover:bg-brand-50 transition-colors"
                >
                  <span className="text-brand-600 font-medium text-sm">{po.po_number}</span>
                  <StatusBadge status={po.status} />
                </Link>
              ))}
            </div>
          )}

          {canApproveReject && (
            <div className="mt-5 pt-5 border-t border-slate-100 space-y-3">
              <div className="text-sm font-semibold text-slate-800">Approval Decision</div>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Comment (optional to approve, required to reject)"
                rows={2}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                  className="text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 disabled:opacity-60"
                >
                  Approve
                </button>
                <button
                  onClick={() => {
                    if (!comment.trim()) {
                      setError("Add a reason in the comment box before rejecting.");
                      return;
                    }
                    setError("");
                    rejectMutation.mutate();
                  }}
                  disabled={rejectMutation.isPending}
                  className="text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2 disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-sm font-semibold text-slate-800 mb-4">Status History</div>
          <div className="space-y-4">
            {pr.status_history.map((h, idx) => (
              <div key={h.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="w-2.5 h-2.5 rounded-full bg-brand-500 mt-1" />
                  {idx < pr.status_history.length - 1 && <span className="w-px flex-1 bg-slate-200" />}
                </div>
                <div className="pb-4">
                  <div className="text-sm font-medium text-slate-800">{h.to_status}</div>
                  {h.comment && <div className="text-xs text-slate-500 mt-0.5">{h.comment}</div>}
                  <div className="text-xs text-slate-400 mt-0.5">
                    {h.changed_by_name} · {new Date(h.changed_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title={`Delete ${pr.pr_number}?`}
        message="This draft purchase request will be permanently deleted. This can't be undone."
        confirmLabel="Delete"
        danger
        isConfirming={deleteMutation.isPending}
        onConfirm={() => {
          setConfirmDeleteOpen(false);
          deleteMutation.mutate();
        }}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
