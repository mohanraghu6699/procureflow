import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { changePassword } from "../api/endpoints";
import { getErrorMessage } from "../api/client";

interface ChangePasswordModalProps {
  open: boolean;
  onClose: () => void;
  // The user cannot dismiss the dialog: an admin set their password and they must choose their own.
  required?: boolean;
  onChanged?: () => void;
}

export function ChangePasswordModal({ open, onClose, required = false, onChanged }: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  function handleClose() {
    setError("");
    setSuccess(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    onClose();
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation don't match");
      return;
    }
    mutation.mutate();
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="fixed inset-0 bg-slate-900/40" onClick={required ? undefined : handleClose} />
      <div className="relative bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-sm p-5">
        <div className="text-sm font-semibold text-slate-900 mb-4">
          {required ? "Choose a new password" : "Change Password"}
        </div>
        {required && !success && (
          <p className="text-sm text-slate-500 -mt-2 mb-4">
            Your password was set by an administrator. Choose your own to continue.
          </p>
        )}

        {success ? (
          <div className="space-y-4">
            <div className="text-sm text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">
              Password updated successfully.
            </div>
            <button
              onClick={() => {
                handleClose();
                onChanged?.();
              }}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-4 py-2.5"
            >
              {required ? "Continue" : "Done"}
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3" autoComplete="off">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Current Password *</label>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">New Password *</label>
              <input
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Confirm New Password *</label>
              <input
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

            <div className="flex justify-end gap-2 pt-1">
              {!required && (
                <button
                  type="button"
                  onClick={handleClose}
                  className="text-sm text-slate-600 border border-slate-200 rounded-lg px-3.5 py-2 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={mutation.isPending}
                className="text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-3.5 py-2 disabled:opacity-60"
              >
                {mutation.isPending ? "Updating..." : "Update Password"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
