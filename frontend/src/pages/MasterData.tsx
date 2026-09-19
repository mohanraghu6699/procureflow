import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCategory,
  createDepartment,
  createVendor,
  deleteCategory,
  deleteDepartment,
  deleteVendor,
  fetchCategories,
  fetchDepartments,
  fetchVendors,
  reactivateCategory,
  reactivateDepartment,
  reactivateVendor,
  updateVendorCategories,
} from "../api/endpoints";
import { getErrorMessage } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { CategoryMultiSelect } from "../components/CategoryMultiSelect";
import { VendorCategoriesModal } from "../components/VendorCategoriesModal";
import type { Category, Vendor } from "../types";

type MasterDataKind = "department" | "category" | "vendor";

interface MasterDataItem {
  id: string;
  name: string;
  is_active: boolean;
}

function VendorsCard({
  vendors,
  categories,
  onAdd,
  onRequestDelete,
  onRestore,
  onEditCategories,
  isAdding,
}: {
  vendors: Vendor[] | undefined;
  categories: Category[];
  onAdd: (name: string, categoryIds: string[]) => void;
  onRequestDelete: (item: PendingDelete) => void;
  onRestore: (id: string) => void;
  onEditCategories: (vendor: Vendor) => void;
  isAdding: boolean;
}) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const activeCategories = categories.filter((c) => c.is_active);
  const categoryName = new Map(categories.map((c) => [c.id, c.name]));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onAdd(name.trim(), selected);
    setName("");
    setSelected([]);
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col md:min-h-0">
      <div className="text-sm font-semibold text-slate-800 mb-3">Vendors</div>
      <form onSubmit={handleSubmit} className="space-y-2 mb-4">
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Add vendor..."
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={isAdding}
            className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-3 py-2 disabled:opacity-60"
          >
            Add
          </button>
        </div>
        <CategoryMultiSelect
          options={activeCategories}
          selected={selected}
          onChange={setSelected}
          placeholder="Categories this vendor supplies"
        />
      </form>
      <div className="space-y-1.5 max-h-96 overflow-y-auto md:max-h-none md:flex-1 md:min-h-0">
        {vendors?.map((vendor) => (
          <div
            key={vendor.id}
            className={`text-sm rounded-lg px-3 py-2 ${
              vendor.is_active ? "bg-slate-50 text-slate-700 hover:bg-slate-100" : "bg-slate-50/60 text-slate-400"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                {vendor.name}
                {!vendor.is_active && (
                  <span className="text-[10px] uppercase tracking-wide bg-slate-200 text-slate-500 rounded-full px-1.5 py-0.5">
                    Inactive
                  </span>
                )}
              </span>
              <span className="flex items-center gap-3">
                {vendor.is_active && (
                  <button
                    onClick={() => onEditCategories(vendor)}
                    className="text-brand-600 hover:text-brand-700 text-xs font-medium"
                  >
                    Categories
                  </button>
                )}
                {vendor.is_active ? (
                  <button
                    onClick={() => onRequestDelete({ kind: "vendor", id: vendor.id, name: vendor.name })}
                    className="text-slate-400 hover:text-red-600 text-xs font-medium"
                  >
                    Remove
                  </button>
                ) : (
                  <button
                    onClick={() => onRestore(vendor.id)}
                    className="text-brand-600 hover:text-brand-700 text-xs font-medium"
                  >
                    Restore
                  </button>
                )}
              </span>
            </div>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {vendor.category_ids.length === 0 ? (
                <span className="text-[11px] text-amber-600">No categories — won't appear in any vendor list</span>
              ) : (
                vendor.category_ids.map((id) => (
                  <span key={id} className="text-[11px] bg-white border border-slate-200 text-slate-500 rounded-full px-2 py-0.5">
                    {categoryName.get(id) ?? "Unknown"}
                  </span>
                ))
              )}
            </div>
          </div>
        ))}
        {vendors?.length === 0 && <div className="text-xs text-slate-400 px-1">None yet</div>}
      </div>
    </div>
  );
}

interface PendingDelete {
  kind: MasterDataKind;
  id: string;
  name: string;
}

function SimpleListCard({
  title,
  kind,
  items,
  onAdd,
  onRequestDelete,
  onRestore,
  isAdding,
}: {
  title: string;
  kind: MasterDataKind;
  items: MasterDataItem[] | undefined;
  onAdd: (name: string) => void;
  onRequestDelete: (item: PendingDelete) => void;
  onRestore: (id: string) => void;
  isAdding: boolean;
}) {
  const [value, setValue] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    onAdd(value.trim());
    setValue("");
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col md:min-h-0">
      <div className="text-sm font-semibold text-slate-800 mb-3">{title}</div>
      <form onSubmit={handleSubmit} className="flex gap-2 mb-4">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={`Add ${title.toLowerCase().slice(0, -1)}...`}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={isAdding}
          className="bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-3 py-2 disabled:opacity-60"
        >
          Add
        </button>
      </form>
      <div className="space-y-1.5 max-h-96 overflow-y-auto md:max-h-none md:flex-1 md:min-h-0">
        {items?.map((item) => (
          <div
            key={item.id}
            className={`flex items-center justify-between text-sm rounded-lg px-3 py-2 ${
              item.is_active ? "bg-slate-50 text-slate-700 hover:bg-slate-100" : "bg-slate-50/60 text-slate-400"
            }`}
          >
            <span className="flex items-center gap-2">
              {item.name}
              {!item.is_active && (
                <span className="text-[10px] uppercase tracking-wide bg-slate-200 text-slate-500 rounded-full px-1.5 py-0.5">
                  Inactive
                </span>
              )}
            </span>
            {item.is_active ? (
              <button
                onClick={() => onRequestDelete({ kind, id: item.id, name: item.name })}
                className="text-slate-400 hover:text-red-600 text-xs font-medium"
              >
                Remove
              </button>
            ) : (
              <button
                onClick={() => onRestore(item.id)}
                className="text-brand-600 hover:text-brand-700 text-xs font-medium"
              >
                Restore
              </button>
            )}
          </div>
        ))}
        {items?.length === 0 && <div className="text-xs text-slate-400 px-1">None yet</div>}
      </div>
    </div>
  );
}

export function MasterData() {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [editingVendor, setEditingVendor] = useState<Vendor | null>(null);

  const departmentsQuery = useQuery({
    queryKey: ["departments", "all"],
    queryFn: () => fetchDepartments(true),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories", "all"],
    queryFn: () => fetchCategories(true),
  });
  const vendorsQuery = useQuery({ queryKey: ["vendors", "all"], queryFn: () => fetchVendors(true) });

  const onError = (err: unknown) => setError(getErrorMessage(err));

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["departments"] });
    queryClient.invalidateQueries({ queryKey: ["categories"] });
    queryClient.invalidateQueries({ queryKey: ["vendors"] });
  }

  const departmentAdd = useMutation({ mutationFn: createDepartment, onSuccess: invalidateAll, onError });
  const departmentDelete = useMutation({ mutationFn: deleteDepartment, onSuccess: invalidateAll, onError });
  const departmentRestore = useMutation({ mutationFn: reactivateDepartment, onSuccess: invalidateAll, onError });

  const categoryAdd = useMutation({ mutationFn: createCategory, onSuccess: invalidateAll, onError });
  const categoryDelete = useMutation({ mutationFn: deleteCategory, onSuccess: invalidateAll, onError });
  const categoryRestore = useMutation({ mutationFn: reactivateCategory, onSuccess: invalidateAll, onError });

  const vendorAdd = useMutation({
    mutationFn: ({ name, categoryIds }: { name: string; categoryIds: string[] }) =>
      createVendor({ name, category_ids: categoryIds }),
    onSuccess: invalidateAll,
    onError,
  });
  const vendorSetCategories = useMutation({
    mutationFn: ({ id, categoryIds }: { id: string; categoryIds: string[] }) =>
      updateVendorCategories(id, categoryIds),
    onSuccess: () => {
      setEditingVendor(null);
      invalidateAll();
    },
    onError,
  });
  const vendorDelete = useMutation({ mutationFn: deleteVendor, onSuccess: invalidateAll, onError });
  const vendorRestore = useMutation({ mutationFn: reactivateVendor, onSuccess: invalidateAll, onError });

  const deleteMutationByKind: Record<MasterDataKind, typeof departmentDelete> = {
    department: departmentDelete,
    category: categoryDelete,
    vendor: vendorDelete,
  };
  const restoreMutationByKind: Record<MasterDataKind, typeof departmentRestore> = {
    department: departmentRestore,
    category: categoryRestore,
    vendor: vendorRestore,
  };

  function handleConfirmDelete() {
    if (!pendingDelete) return;
    deleteMutationByKind[pendingDelete.kind].mutate(pendingDelete.id);
    setPendingDelete(null);
  }

  return (
    <div className="space-y-4 md:h-full md:flex md:flex-col md:space-y-0 md:gap-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Master Data</h1>
        <p className="text-sm text-slate-500">
          Manage departments, categories, and vendors. Removed items are deactivated, not deleted — restore
          them any time.
        </p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-3 md:grid-rows-[minmax(0,1fr)] md:flex-1 md:min-h-0 gap-4">
        <SimpleListCard
          title="Departments"
          kind="department"
          items={departmentsQuery.data}
          onAdd={(name) => departmentAdd.mutate(name)}
          onRequestDelete={setPendingDelete}
          onRestore={(id) => restoreMutationByKind.department.mutate(id)}
          isAdding={departmentAdd.isPending}
        />
        <SimpleListCard
          title="Categories"
          kind="category"
          items={categoriesQuery.data}
          onAdd={(name) => categoryAdd.mutate(name)}
          onRequestDelete={setPendingDelete}
          onRestore={(id) => restoreMutationByKind.category.mutate(id)}
          isAdding={categoryAdd.isPending}
        />
        <VendorsCard
          vendors={vendorsQuery.data}
          categories={categoriesQuery.data ?? []}
          onAdd={(name, categoryIds) => vendorAdd.mutate({ name, categoryIds })}
          onRequestDelete={setPendingDelete}
          onRestore={(id) => restoreMutationByKind.vendor.mutate(id)}
          onEditCategories={setEditingVendor}
          isAdding={vendorAdd.isPending}
        />
      </div>

      {editingVendor && (
        <VendorCategoriesModal
          key={editingVendor.id}
          vendorName={editingVendor.name}
          categories={(categoriesQuery.data ?? []).filter((c) => c.is_active)}
          initialSelected={editingVendor.category_ids}
          isSaving={vendorSetCategories.isPending}
          onSave={(categoryIds) => vendorSetCategories.mutate({ id: editingVendor.id, categoryIds })}
          onCancel={() => setEditingVendor(null)}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Remove "${pendingDelete?.name}"?`}
        message="It's deactivated, not deleted — existing purchase requests/orders are unaffected, and you can restore it any time from this page."
        confirmLabel="Remove"
        danger
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
