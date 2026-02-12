import { BrowserRouter, Routes, Route } from "react-router-dom";
import LoginPage from "@/components/Auth/LoginPage";
import ProtectedRoute from "@/components/Auth/ProtectedRoute";
import DashboardPage from "@/pages/DashboardPage";
import SettingsPage from "@/pages/SettingsPage";

function ErrorFallback() {
  return (
    <div className="fixed inset-0 bg-[#1a1a2e] flex items-center justify-center text-gray-400">
      <div className="text-center">
        <h2 className="text-xl font-bold mb-2">Something went wrong</h2>
        <button onClick={() => window.location.reload()} className="bg-[#0f3460] rounded px-4 py-2 text-sm hover:bg-[#1a4a8a]">
          Reload
        </button>
      </div>
    </div>
  );
}

export default function App() {
  try {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/settings" element={<ProtectedRoute requiredRole="operator"><SettingsPage /></ProtectedRoute>} />
          <Route path="/*" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    );
  } catch {
    return <ErrorFallback />;
  }
}
