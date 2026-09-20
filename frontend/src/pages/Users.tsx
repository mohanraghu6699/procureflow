import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createUser,
  deactivateUser,
  deleteUser,
  fetchDepartments,
  listUsers,
  reactivateUser,
  resetUserPassword,
} from "../api/endpoints";
import { getErrorMessage } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../context/AuthContext";
import type { User, UserRole } from "../types";

const ROLES: UserRole[] = ["REQUESTER", "APPROVER", "ADMIN"];

const PASSWORD_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*";

function generatePassword(length = 12): string {
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (n) => PASSWORD_CHARS[n % PASSWORD_CHARS.length]).join("");
}

export function Users() {
  const queryClient = useQueryClient();
  const { user: me } = useAuth();
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: () => fetchDepartments() });

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState<UserRole>("REQUESTER");
  const [departmentId, setDepartmentId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createUser({ name, email, password, role, department_id: departmentId || null }),
    onSuccess: (user) => {
      setSuccess(`${user.name} created successfully.`);
      setName("");
      setEmail("");
      setPassword("");
      setShowPassword(false);
      setRole("REQUESTER");
      setDepartmentId("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const refreshUsers = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const resetMutation = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) => resetUserPassword(id, password),
    onSuccess: (u) => {
      setResetTarget(null);
      setNotice(`Password for ${u.name} reset. They will be asked to choose a new one at their next sign-in.`);
      refreshUsers();
    },
  });

  const activeMutation = useMutation({
    mutationFn: ({ id, activate }: { id: string; activate: boolean }) =>
      activate ? reactivateUser(id) : deactivateUser(id),
    onSuccess: (u) => {
      setDeactivateTarget(null);
      setNotice(`${u.name} ${u.is_active ? "reactivated" : "deactivated"}.`);
      refreshUsers();
    },
    onError: (err) => {
      setDeactivateTarget(null);
      setActionError(getErrorMessage(err));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      setNotice(`${deleteTarget?.name} deleted.`);
      setDeleteTarget(null);
      refreshUsers();
    },
    onError: (err) => {
      setDeleteTarget(null);
      setActionError(getErrorMessage(err)); // e.g. "This user has 3 records ... deactivate the account instead"
    },
  });

  function startAction(action: () => void) {
    setNotice("");
    setActionError("");
    action();
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    mutation.mutate();
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Users</h1>
        <p className="text-sm text-slate-500">Manage user accounts and role assignments</p>
      </div>

      {notice && <div className="text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{notice}</div>}
      {actionError && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{actionError}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="text-sm font-semibold text-slate-800 mb-3">New User</div>
          <form onSubmit={handleSubmit} className="space-y-3" autoComplete="off">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Full Name *</label>
              <input
                required
                minLength={2}
                autoComplete="off"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email *</label>
              <input
                type="email"
                required
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password *</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={6}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 pl-3 pr-16 py-2 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setPassword(generatePassword());
                    setShowPassword(true);
                  }}
                  className="text-sm text-brand-600 border border-brand-200 rounded-lg px-3 py-2 hover:bg-brand-50 whitespace-nowrap"
                >
                  Generate
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Share this with the new user directly — it isn't emailed. They choose their own at first sign-in.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Role *</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Department</label>
              <select
                value={departmentId}
                onChange={(e) => setDepartmentId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">None</option>
                {departmentsQuery.data?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
            {success && <div className="text-sm text-emerald-600 bg-emerald-50 rounded-lg px-3 py-2">{success}</div>}

            <button
              type="submit"
              disabled={mutation.isPending}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg px-4 py-2.5 disabled:opacity-60"
            >
              {mutation.isPending ? "Creating..." : "Create User"}
            </button>
          </form>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 lg:col-span-2 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">
            All Users
          </div>
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400 border-b border-slate-100 bg-slate-50">
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Email</th>
                <th className="px-4 py-2.5 font-medium">Role</th>
                <th className="px-4 py-2.5 font-medium">Department</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {usersQuery.data?.map((u) => (
                <tr key={u.id} className="border-b border-slate-100 last:border-0 hover:bg-brand-50 transition-colors">
                  <td className="px-4 py-3 text-slate-800 font-medium">{u.name}</td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                  <td className="px-4 py-3 text-slate-600">{u.role}</td>
                  <td className="px-4 py-3 text-slate-600">{u.department_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.is_active === false ? "bg-slate-200 text-slate-600" : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {u.is_active === false ? "Inactive" : "Active"}
                    </span>
                    {u.must_change_password && (
                      <div className="text-[11px] text-amber-600 mt-0.5">Must change password</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {u.id === me?.id ? (
                      <span className="text-xs text-slate-400">You</span>
                    ) : (
                      <div className="flex justify-end gap-3 text-xs">
                        <button
                          onClick={() => startAction(() => setResetTarget(u))}
                          className="text-brand-600 hover:underline"
                        >
                          Reset password
                        </button>
                        {u.is_active === false ? (
                          <button
                            onClick={() => startAction(() => activeMutation.mutate({ id: u.id, activate: true }))}
                            className="text-emerald-700 hover:underline"
                          >
                            Reactivate
                          </button>
                        ) : (
                          <button
                            onClick={() => startAction(() => setDeactivateTarget(u))}
                            className="text-amber-700 hover:underline"
                          >
                            Deactivate
                          </button>
                        )}
                        <button
                          onClick={() => startAction(() => setDeleteTarget(u))}
                          className="text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      </div>

      {resetTarget && (
        <ResetPasswordDialog
          user={resetTarget}
          isSubmitting={resetMutation.isPending}
          error={resetMutation.isError ? getErrorMessage(resetMutation.error) : undefined}
          onConfirm={(password) => resetMutation.mutate({ id: resetTarget.id, password })}
          onCancel={() => {
            resetMutation.reset();
            setResetTarget(null);
          }}
        />
      )}
      <ConfirmDialog
        open={deactivateTarget !== null}
        title={`Deactivate ${deactivateTarget?.name}?`}
        message="They will be signed out straight away and can't sign in until you reactivate them. Everything they did stays on record."
        confirmLabel="Deactivate"
        danger
        isConfirming={activeMutation.isPending}
        onConfirm={() => deactivateTarget && activeMutation.mutate({ id: deactivateTarget.id, activate: false })}
        onCancel={() => setDeactivateTarget(null)}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title={`Delete ${deleteTarget?.name}?`}
        message="This removes the account for good, so the email address can be used again. It is only possible for a user who has never created or changed anything; otherwise deactivate them instead."
        confirmLabel="Delete"
        danger
        isConfirming={deleteMutation.isPending}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

function ResetPasswordDialog({
  user,
  isSubmitting,
  error,
  onConfirm,
  onCancel,
}: {
  user: User;
  isSubmitting: boolean;
  error?: string;
  onConfirm: (password: string) => void;
  onCancel: () => void;
}) {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="fixed inset-0 bg-slate-900/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-5">
        <div className="text-sm font-semibold text-slate-900">Reset password for {user.name}</div>
        <p className="text-sm text-slate-500 mt-1">
          Set a temporary password and share it with them directly. They will be asked to choose their own at their next
          sign-in, and any session they have open stops working now.
        </p>

        <label className="block text-sm font-medium text-slate-700 mt-4 mb-1">Temporary password *</label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              autoFocus
              type={show ? "text" : "password"}
              minLength={6}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 pl-3 pr-16 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
            >
              {show ? "Hide" : "Show"}
            </button>
          </div>
          <button
            type="button"
            onClick={() => {
              setPassword(generatePassword());
              setShow(true);
            }}
            className="text-sm text-brand-600 border border-brand-200 rounded-lg px-3 py-2 hover:bg-brand-50 whitespace-nowrap"
          >
            Generate
          </button>
        </div>

        {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mt-3">{error}</div>}

        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onCancel}
            className="text-sm text-slate-600 border border-slate-200 rounded-lg px-3.5 py-2 hover:bg-slate-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(password)}
            disabled={isSubmitting || password.length < 6}
            className="text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-lg px-3.5 py-2 disabled:opacity-50"
          >
            {isSubmitting ? "Please wait..." : "Reset password"}
          </button>
        </div>
      </div>
    </div>
  );
}
