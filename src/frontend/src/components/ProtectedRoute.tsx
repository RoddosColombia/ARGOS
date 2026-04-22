import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { isSessionValid, readSession } from "@/lib/auth";

interface Props {
  children: ReactNode;
}

export function ProtectedRoute({ children }: Props) {
  const location = useLocation();
  const session = readSession();
  if (!isSessionValid(session)) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}
