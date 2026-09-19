import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import { Approvals } from "./pages/Approvals";
import { Dashboard } from "./pages/Dashboard";
import { Deliveries } from "./pages/Deliveries";
import { Login } from "./pages/Login";
import { MasterData } from "./pages/MasterData";
import { Users } from "./pages/Users";
import { PODetail } from "./pages/PurchaseOrders/PODetail";
import { POForm } from "./pages/PurchaseOrders/POForm";
import { POList } from "./pages/PurchaseOrders/POList";
import { PRDetail } from "./pages/PurchaseRequests/PRDetail";
import { PRForm } from "./pages/PurchaseRequests/PRForm";
import { PRList } from "./pages/PurchaseRequests/PRList";

function LoginRoute() {
  const { user } = useAuth();
  if (user) return <Navigate to="/dashboard" replace />;
  return <Login />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />

        <Route path="/purchase-requests" element={<PRList />} />
        <Route path="/purchase-requests/new" element={<PRForm />} />
        <Route path="/purchase-requests/:id/edit" element={<PRForm />} />
        <Route path="/purchase-requests/:id" element={<PRDetail />} />

        <Route
          path="/approvals"
          element={
            <ProtectedRoute roles={["APPROVER", "ADMIN"]}>
              <Approvals />
            </ProtectedRoute>
          }
        />

        <Route path="/purchase-orders" element={<POList />} />
        <Route
          path="/purchase-orders/new"
          element={
            <ProtectedRoute roles={["APPROVER", "ADMIN"]}>
              <POForm />
            </ProtectedRoute>
          }
        />
        <Route path="/purchase-orders/:id" element={<PODetail />} />

        <Route
          path="/deliveries"
          element={
            <ProtectedRoute roles={["APPROVER", "ADMIN"]}>
              <Deliveries />
            </ProtectedRoute>
          }
        />

        <Route
          path="/master-data"
          element={
            <ProtectedRoute roles={["ADMIN"]}>
              <MasterData />
            </ProtectedRoute>
          }
        />

        <Route
          path="/users"
          element={
            <ProtectedRoute roles={["ADMIN"]}>
              <Users />
            </ProtectedRoute>
          }
        />

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
