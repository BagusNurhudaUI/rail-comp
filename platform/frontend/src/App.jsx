import { Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";

import AppLayout from "./components/AppLayout";
import { useAuth } from "./context/AuthContext";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import MaintenancePage from "./pages/MaintenancePage";
import ComponentsPage from "./pages/ComponentsPage";
import ComponentHistory from "./pages/ComponentHistory";
import MasterLocomotives from "./pages/MasterLocomotives";
import MasterComponents from "./pages/MasterComponents";
import Reports from "./pages/Reports";
import Users from "./pages/Users";
import Settings from "./pages/Settings";

function Protected({ children }) {
  const { user, ready } = useAuth();

  if (!ready) {
    return (
      <div style={{ display: "grid", placeItems: "center", height: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        path="/"
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="lokomotif" element={<MaintenancePage />} />
        <Route path="komponen" element={<ComponentsPage />} />
        <Route path="riwayat-komponen" element={<ComponentHistory />} />
        <Route path="perawatan" element={<MaintenancePage variant="perawatan" />} />
        <Route path="master/lokomotif" element={<MasterLocomotives />} />
        <Route path="master/komponen" element={<MasterComponents />} />
        <Route path="laporan" element={<Reports />} />
        <Route path="pengguna" element={<Users />} />
        <Route path="pengaturan" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
