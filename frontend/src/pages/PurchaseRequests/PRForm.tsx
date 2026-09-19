import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  createPurchaseRequest,
  fetchCategories,
  fetchDepartments,
  fetchVendors,
  getPurchaseRequest,
  updatePurchaseRequest,
} from "../../api/endpoints";
import { getErrorMessage } from "../../api/client";

const CURRENCIES = ["AED", "USD", "EUR", "GBP", "INR"];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function PRForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [departmentId, setDepartmentId] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("AED");
  const [requiredDate, setRequiredDate] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [error, setError] = useState("");

  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: () => fetchDepartments() });
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: () => fetchCategories() });
  const vendorsQuery = useQuery({
    queryKey: ["vendors", "by-category", categoryId],
    queryFn: () => fetchVendors(false, categoryId),
    enabled: Boolean(categoryId),
  });
  const prQuery = useQuery({
    queryKey: ["purchase-request", id],
    queryFn: () => getPurchaseRequest(id as string),
    enabled: isEdit,
  });

  useEffect(() => {
    if (prQuery.data) {
      setDepartmentId(prQuery.data.department_id);
      setDescription(prQuery.data.description);
      setCategoryId(prQuery.data.category_id);
      setAmount(prQuery.data.amount);
      setCurrency(prQuery.data.currency);
      setRequiredDate(prQuery.data.required_date.slice(0, 10));
      setVendorId(prQuery.data.vendor_id || "");
    }
  }, [prQuery.data]);

  const original = prQuery.data;
  const unchanged =
    isEdit &&
    original !== undefined &&
    departmentId === original.department_id &&
    description.trim() === original.description.trim() &&
    categoryId === original.category_id &&
    Number(amount) === Number(original.amount) &&
    currency === original.currency &&
    requiredDate === original.required_date.slice(0, 10) &&
    vendorId === (original.vendor_id || "");

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        department_id: departmentId,
        description,
        category_id: categoryId,
        amount: Number(amount),
        currency,
        required_date: new Date(requiredDate).toISOString(),
        vendor_id: vendorId || null,
      };
      if (isEdit) {
        return updatePurchaseRequest(id as string, payload);
      }
      return createPurchaseRequest(payload);
    },
    onSuccess: (pr) => {
      queryClient.invalidateQueries({ queryKey: ["purchase-requests"] });
      navigate(`/purchase-requests/${pr.id}`);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    mutation.mutate();
  }

  if (isEdit && prQuery.isLoading) {
    return <div className="text-sm text-slate-500">Loading...</div>;
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">
        {isEdit ? "Edit Purchase Request" : "New Purchase Request"}
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        {isEdit ? "Update the details of your draft request" : "Fill in the details for your purchase request"}
      </p>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Description *</label>
          <textarea
            required
            minLength={3}
            maxLength={500}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="What are you requesting and why?"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Department *</label>
            <select
              required
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Select department</option>
              {departmentsQuery.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Category *</label>
            <select
              required
              value={categoryId}
              onChange={(e) => {
                setCategoryId(e.target.value);
                setVendorId("");
              }}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Select category</option>
              {categoriesQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-slate-700 mb-1">Amount *</label>
            <input
              type="number"
              required
              min={0.01}
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="0.00"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Required Date *</label>
            <input
              type="date"
              required
              min={todayIso()}
              value={requiredDate}
              onChange={(e) => setRequiredDate(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Preferred Vendor</label>
            <select
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              disabled={!categoryId}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50 disabled:text-slate-400"
            >
              <option value="">
                {!categoryId
                  ? "Select a category first"
                  : vendorsQuery.data?.length === 0
                    ? "No vendors supply this category"
                    : "No preference"}
              </option>
              {vendorsQuery.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={mutation.isPending || unchanged}
            title={unchanged ? "Change something to save" : undefined}
            className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-5 py-2.5 disabled:opacity-60"
          >
            {mutation.isPending ? "Saving..." : isEdit ? "Save Changes" : "Create Draft"}
          </button>
          {unchanged && <span className="text-xs text-slate-400">Nothing changed yet</span>}
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
