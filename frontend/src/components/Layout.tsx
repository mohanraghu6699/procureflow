import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { fetchDashboardSummary } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: "🏠" },
  { to: "/purchase-requests", label: "Purchase Requests", icon: "📄" },
  { to: "/approvals", label: "Approvals", icon: "✅", roles: ["APPROVER", "ADMIN"] },
  { to: "/purchase-orders", label: "Purchase Orders", icon: "📦" },
  { to: "/deliveries", label: "Deliveries", icon: "🚚", roles: ["APPROVER", "ADMIN"] },
  { to: "/master-data", label: "Master Data", icon: "🗂️", roles: ["ADMIN"] },
  { to: "/users", label: "Users", icon: "👥", roles: ["ADMIN"] },
];

const COLLAPSE_KEY = "sidebar-collapsed";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // storage unavailable: the choice just won't persist
      }
      return next;
    });
  }

  const canApprove = user?.role === "APPROVER" || user?.role === "ADMIN";
  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
    enabled: canApprove,
    refetchInterval: 30000,
  });
  const pendingApprovals = summaryQuery.data?.pending_approval ?? 0;

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const visibleItems = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(user?.role || ""));
  // "collapsed" only applies from md up; the mobile drawer always shows full labels.
  const hideWhenCollapsed = collapsed ? "md:hidden" : "";

  return (
    <div className="flex h-[100dvh]">
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-slate-900/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 ${
          collapsed ? "md:w-16" : "md:w-56"
        } bg-slate-900 text-slate-200 flex flex-col shrink-0 transition-[width,transform] duration-200 md:relative md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <button
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="hidden md:flex absolute -right-3 top-5 z-50 w-6 h-6 items-center justify-center rounded-full bg-white border border-slate-300 text-slate-500 shadow-sm hover:text-brand-600 hover:border-brand-500 transition-colors"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transition-transform duration-200 ${collapsed ? "rotate-180" : ""}`}
          >
            <path d="M7.5 2.5 4 6l3.5 3.5" />
          </svg>
        </button>
        <div
          className={`px-5 py-4 flex items-center gap-2 border-b border-slate-800 ${
            collapsed ? "md:justify-center md:px-2" : ""
          }`}
        >
          <div className="w-8 h-8 shrink-0 rounded-lg bg-brand-500 flex items-center justify-center font-bold text-white">
            P
          </div>
          <div className={hideWhenCollapsed}>
            <div className="font-semibold text-white leading-tight">ProcureFlow</div>
            <div className="text-[11px] text-slate-400 leading-tight">Purchase to Pay</div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
            className="ml-auto text-slate-400 hover:text-white md:hidden"
          >
            ✕
          </button>
        </div>

        <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.label}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  collapsed ? "md:justify-center md:px-0" : ""
                } ${isActive ? "bg-brand-500 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`
              }
            >
              <span>{item.icon}</span>
              <span className={`whitespace-nowrap ${hideWhenCollapsed}`}>{item.label}</span>
              {item.to === "/approvals" && pendingApprovals > 0 && (
                <span
                  aria-label={`${pendingApprovals} pending`}
                  className={`rounded-full bg-red-500 text-white font-semibold flex items-center justify-center ${
                    collapsed
                      ? "ml-auto md:ml-0 md:absolute md:top-0.5 md:right-1.5 min-w-[20px] md:min-w-[16px] h-5 md:h-4 px-1.5 md:px-1 text-[11px] md:text-[10px]"
                      : "ml-auto min-w-[20px] h-5 px-1.5 text-[11px]"
                  }`}
                >
                  {pendingApprovals}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={`px-4 py-3 text-[11px] text-slate-500 border-t border-slate-800 ${hideWhenCollapsed}`}>
          Smarter Procurement
          <br />
          Stronger Business
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <header className="bg-white border-b border-slate-200 h-14 flex items-center px-4 sm:px-5 shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="md:hidden -ml-1 mr-3 p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M3 5h14M3 10h14M3 15h14" />
            </svg>
          </button>

          <div className="ml-auto flex items-center gap-2 sm:gap-4">
            <div className="relative">
              <button onClick={() => setProfileOpen((v) => !v)} className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="text-sm font-medium text-slate-800">{user?.name}</div>
                  <div className="text-xs text-slate-400">{user?.role}</div>
                </div>
                <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold text-sm">
                  {user?.name
                    ?.split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)}
                </div>
              </button>

              {profileOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
                  <div className="absolute right-0 top-full mt-2 w-64 max-w-[calc(100vw-2rem)] bg-white border border-slate-200 rounded-xl shadow-lg z-20 p-4">
                    <div className="text-sm font-semibold text-slate-900">{user?.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5 break-all">{user?.email}</div>
                    <div className="flex items-center gap-2 mt-3 text-xs">
                      <span className="bg-brand-50 text-brand-700 rounded-full px-2 py-0.5 font-medium">
                        {user?.role}
                      </span>
                      {user?.department_name && <span className="text-slate-500">{user.department_name}</span>}
                    </div>
                    <button
                      onClick={() => {
                        setProfileOpen(false);
                        setChangePasswordOpen(true);
                      }}
                      className="w-full text-left text-sm text-slate-600 hover:text-brand-600 mt-4 pt-3 border-t border-slate-100"
                    >
                      Change Password
                    </button>
                  </div>
                </>
              )}
            </div>
            <button
              onClick={handleLogout}
              className="text-sm text-slate-500 hover:text-red-600 border border-slate-200 rounded-lg px-3 py-1.5"
            >
              Logout
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-3 sm:p-4 bg-slate-50">
          <Outlet />
        </main>
      </div>

      <ChangePasswordModal open={changePasswordOpen} onClose={() => setChangePasswordOpen(false)} />
    </div>
  );
}
