import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated, isAuthInitialized } = useAuth();

   // ⏳ Wait for localStorage hydration
  if (!isAuthInitialized) {
    return null; // or loading spinner
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
