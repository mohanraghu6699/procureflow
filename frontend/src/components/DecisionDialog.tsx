import { useState } from "react";

interface DecisionDialogProps {
  mode: "approve" | "reject";
  title: string;
  subtitle?: string;
  isSubmitting: boolean;
  error?: string;
  onConfirm: (comment: string) => void;
  onCancel: () => void;
}

export function DecisionDialog({ mode, title, subtitle, isSubmitting, error, onConfirm, onCancel }: DecisionDialogProps) {
  const [comment, setComment] = useState("");
  const isReject = mode === "reject";
  const canSubmit = !isSubmitting && (!isReject || comment.trim().length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="fixed inset-0 bg-slate-900/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-5">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        {subtitle && <div className="text-sm text-slate-500 mt-1 break-words">{subtitle}</div>}

        <label className="block text-sm font-medium text-slate-700 mt-4 mb-1">
          {isReject ? "Reason for rejection *" : "Comment (optional)"}
        </label>
        <textarea
          autoFocus
          rows={3}
          maxLength={500}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder={isReject ? "Tell the requester what needs to change" : "Add a note for the record"}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />

        {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mt-3">{error}</div>}

        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onCancel}
            className="text-sm text-slate-600 border border-slate-200 rounded-lg px-3.5 py-2 hover:bg-slate-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(comment.trim())}
            disabled={!canSubmit}
            className={`text-sm text-white rounded-lg px-3.5 py-2 disabled:opacity-50 ${
              isReject ? "bg-red-600 hover:bg-red-700" : "bg-emerald-600 hover:bg-emerald-700"
            }`}
          >
            {isSubmitting ? "Please wait..." : isReject ? "Reject" : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
