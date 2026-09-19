import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getPurchaseOrder, recordDelivery } from "../../api/endpoints";
import { getErrorMessage } from "../../api/client";
import { BackLink } from "../../components/BackLink";
import { StatusBadge } from "../../components/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import type { DeliveryStatus } from "../../types";
import { DueBadge } from "../../components/DueBadge";
import { deliveryTiming, formatCurrency, localDate, openOrderDue } from "../../utils/format";



export function PODetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [deliveryStatus, setDeliveryStatus] = useState<DeliveryStatus>("IN_TRANSIT");
  const [deliveryDate, setDeliveryDate] = useState(localDate(new Date()));
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState("");

  const poQuery = useQuery({ queryKey: ["purchase-order", id], queryFn: () => getPurchaseOrder(id as string) });

  const mutation = useMutation({
    mutationFn: () =>
      recordDelivery(id as string, {
        status: deliveryStatus,
        delivery_date:
          deliveryStatus === "IN_TRANSIT"
            ? null
            : new Date(deliveryStatus === "DELIVERED" ? deliveryDate : localDate(new Date())).toISOString(),
        remarks: remarks || undefined,
      }),
    onSuccess: () => {
      setRemarks("");
      queryClient.invalidateQueries({ queryKey: ["purchase-order", id] });
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (poQuery.isLoading || !poQuery.data) {
    return <div className="text-sm text-slate-500">Loading...</div>;
  }

  const po = poQuery.data;
  const canUpdateDelivery = (user?.role === "APPROVER" || user?.role === "ADMIN") && po.status !== "COMPLETED";
  const finalDelivery = [...po.deliveries].reverse().find((d) => d.status === "DELIVERED" && d.delivery_date);
  const requiredBadge =
    po.status !== "COMPLETED"
      ? openOrderDue(po.required_date)
      : finalDelivery?.delivery_date
        ? deliveryTiming(finalDelivery.delivery_date, po.required_date)
        : null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    mutation.mutate();
  }

  return (
    <div className="space-y-4">
      <BackLink to="/purchase-orders" label="Purchase Orders" />
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-900">{po.po_number}</h1>
            <StatusBadge status={po.status} />
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Against{" "}
            <Link to={`/purchase-requests/${po.pr_id}`} className="text-brand-600 font-medium">
              {po.pr_number}
            </Link>
          </p>
        </div>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-sm font-semibold text-slate-800 mb-4">Order Details</div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-y-4 text-sm">
              <div>
                <dt className="text-slate-400">Vendor</dt>
                <dd className="text-slate-800 font-medium">{po.vendor_name}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Amount</dt>
                <dd className="text-slate-800 font-medium">
                  {po.currency} {formatCurrency(po.amount)}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Required By</dt>
                <dd className="text-slate-800 font-medium flex flex-wrap items-center gap-2">
                  {new Date(po.required_date).toLocaleDateString()}
                  {requiredBadge && <DueBadge info={requiredBadge} />}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Created By</dt>
                <dd className="text-slate-800 font-medium">{po.created_by_name}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Created</dt>
                <dd className="text-slate-800 font-medium">{new Date(po.created_at).toLocaleString()}</dd>
              </div>
            </dl>
          </div>

          {canUpdateDelivery && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="text-sm font-semibold text-slate-800 mb-4">Update Delivery Status</div>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
                    <select
                      value={deliveryStatus}
                      onChange={(e) => setDeliveryStatus(e.target.value as DeliveryStatus)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    >
                      <option value="IN_TRANSIT">In transit</option>
                      <option value="PARTIAL">Partially delivered</option>
                      <option value="DELIVERED">Delivered (completes order)</option>
                    </select>
                  </div>
                  {deliveryStatus === "DELIVERED" ? (
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Delivery Date *</label>
                      <input
                        type="date"
                        required
                        min={localDate(new Date(po.created_at))}
                        max={localDate(new Date())}
                        value={deliveryDate}
                        onChange={(e) => setDeliveryDate(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      />
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 sm:self-end sm:pb-2.5">
                      {deliveryStatus === "IN_TRANSIT"
                        ? "Shipment on its way. Recorded now, under your name."
                        : "Part of the order received. Recorded today, under your name."}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Remarks</label>
                  <input
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Optional remarks"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
                <button
                  type="submit"
                  disabled={mutation.isPending}
                  className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-4 py-2.5 disabled:opacity-60"
                >
                  {mutation.isPending ? "Saving..." : "Record Delivery Update"}
                </button>
              </form>
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-sm font-semibold text-slate-800 mb-4">Delivery History</div>
          <div className="space-y-4">
            {po.deliveries.length === 0 && <div className="text-sm text-slate-400">No delivery updates yet</div>}
            {[...po.deliveries].reverse().map((d, idx) => (
              <div key={d.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="w-2.5 h-2.5 rounded-full bg-brand-500 mt-1" />
                  {idx < po.deliveries.length - 1 && <span className="w-px flex-1 bg-slate-200" />}
                </div>
                <div className="pb-4">
                  <StatusBadge status={d.status} />
                  {d.delivery_date && (
                    <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-2">
                      <span>Delivery date: {new Date(d.delivery_date).toLocaleDateString()}</span>
                      <DueBadge info={deliveryTiming(d.delivery_date, po.required_date)} />
                    </div>
                  )}
                  {d.remarks && <div className="text-xs text-slate-500">{d.remarks}</div>}
                  <div className="text-xs text-slate-400 mt-0.5">
                    {d.updated_by_name} · {new Date(d.updated_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
