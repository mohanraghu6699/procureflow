import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { createPurchaseOrder, fetchVendors, listPurchaseRequests } from "../../api/endpoints";
import { getErrorMessage } from "../../api/client";

export function POForm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedPrId = searchParams.get("prId") || "";

  const [prId, setPrId] = useState(preselectedPrId);
  const [vendorId, setVendorId] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("AED");
  const [error, setError] = useState("");

  const approvedPRsQuery = useQuery({
    queryKey: ["approved-prs-for-po"],
    queryFn: () => listPurchaseRequests({ status: "APPROVED", page: 1, page_size: 100 }),
  });

  const selectedPR = approvedPRsQuery.data?.items.find((pr) => pr.id === prId);

  const vendorsQuery = useQuery({
    queryKey: ["vendors", "by-category", selectedPR?.category_id],
    queryFn: () => fetchVendors(false, selectedPR?.category_id),
    enabled: Boolean(selectedPR),
  });

  useEffect(() => {
    if (selectedPR) {
      setVendorId(selectedPR.vendor_id || "");
      setAmount(selectedPR.amount);
      setCurrency(selectedPR.currency);
    }
  }, [selectedPR?.id]);

  const mutation = useMutation({
    mutationFn: () =>
      createPurchaseOrder({ pr_id: prId, vendor_id: vendorId, amount: Number(amount), currency }),
    onSuccess: (po) => navigate(`/purchase-orders/${po.id}`),
    onError: (err) => setError(getErrorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    mutation.mutate();
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">New Purchase Order</h1>
      <p className="text-sm text-slate-500 mb-6">Issue a purchase order against an approved purchase request</p>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Approved Purchase Request *</label>
          <select
            required
            value={prId}
            onChange={(e) => setPrId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Select an approved purchase request</option>
            {approvedPRsQuery.data?.items.map((pr) => (
              <option key={pr.id} value={pr.id}>
                {pr.pr_number} — {pr.description} ({pr.currency} {pr.amount})
              </option>
            ))}
          </select>
          {approvedPRsQuery.data?.items.length === 0 && (
            <p className="text-xs text-amber-600 mt-1">No approved purchase requests are available right now.</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Vendor *</label>
          <select
            required
            value={vendorId}
            onChange={(e) => setVendorId(e.target.value)}
            disabled={!selectedPR}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50 disabled:text-slate-400"
          >
            <option value="">
              {!selectedPR
                ? "Select a purchase request first"
                : vendorsQuery.data?.length === 0
                  ? "No vendors supply this category"
                  : "Select vendor"}
            </option>
            {vendorsQuery.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          {selectedPR && (
            <p className="text-xs text-slate-400 mt-1">
              Only vendors that supply {selectedPR.category_name} are listed.
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-slate-700 mb-1">PO Amount *</label>
            <input
              type="number"
              required
              min={0.01}
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Currency</label>
            <input
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              maxLength={6}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={mutation.isPending || !prId}
            className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-5 py-2.5 disabled:opacity-60"
          >
            {mutation.isPending ? "Creating..." : "Create Purchase Order"}
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="text-sm text-slate-500 hover:text-slate-700 px-4 py-2.5"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
