import { useState } from "react";
import { CategoryMultiSelect } from "./CategoryMultiSelect";

export function VendorCategoriesModal({
  vendorName,
  categories,
  initialSelected,
  isSaving,
  onSave,
  onCancel,
}: {
  vendorName: string;
  categories: { id: string; name: string }[];
  initialSelected: string[];
  isSaving: boolean;
  onSave: (ids: string[]) => void;
  onCancel: () => void;
}) {
  const [selected, setSelected] = useState(initialSelected);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="fixed inset-0 bg-slate-900/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-5">
        <div className="text-sm font-semibold text-slate-900">Categories supplied by {vendorName}</div>
        <div className="text-sm text-slate-500 mt-1 mb-4">
          This vendor only appears in the PR and PO vendor lists for the categories selected here.
        </div>
        <CategoryMultiSelect options={categories} selected={selected} onChange={setSelected} />
        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onCancel}
            className="text-sm text-slate-600 border border-slate-200 rounded-lg px-3.5 py-2 hover:bg-slate-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave(selected)}
            disabled={isSaving}
            className="text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-3.5 py-2 disabled:opacity-60"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
