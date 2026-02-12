import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, hasRole } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (requiredRole && !hasRole(requiredRole)) {
    return <div className="fixed inset-0 bg-[#1a1a2e] flex items-center justify-center text-gray-400 text-lg">Access Denied</div>;
  }
  return <>{children}</>;
}
