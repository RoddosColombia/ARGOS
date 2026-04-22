import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import "./index.css";
import { queryClient } from "@/lib/queryClient";
import { router } from "@/router";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Elemento #root no encontrado en index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
