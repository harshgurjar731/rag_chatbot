import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "sonner"; // ✅ correct Sonner import
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import EvaluationSelection from "./pages/EvaluationSelection";
import EvaluationTimeline from "./pages/EvaluationTimeline";
import RAGOutput from "./pages/RAGOutput";
import ChatbotDetail from "./pages/ChatbotDetail";
import NotFound from "./pages/NotFound";
import SidebarLayout from "./components/SidebarLayout";
import EvaluationDashboard from "./pages/EvaluationDashboard";
import RAGASEvaluationOutput from "./pages/RagaasOutput";
import { DatastoreConfigDetail } from "./pages/DatastoreConfigDetail";
import DatastoreDashboard from "./pages/DatastoreDashboard";
import { AuthProvider } from "./auth-context/AuthContext";
import Login from "./pages/Login";
import ProtectedRoute from "./auth-context/ProtectedRoute";
import About from "./pages/About";
const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<Login />} />

            {/* Protected */}
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<SidebarLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="evaluation" element={<EvaluationDashboard />} />
                {/* <Route path="datastore" element={<DatastoreConfigDetail />} /> */}
                <Route path="datastore2" element={<DatastoreDashboard />} />
                <Route path="about" element={<About/>} />
                <Route path="*" element={<NotFound />} />
              </Route>
              <Route path="evaluation-selection/:id" element={<EvaluationSelection />} />
              <Route path="evaluation-timeline/:id" element={<EvaluationTimeline />} />
              <Route path="rag-output/:id" element={<RAGOutput />} />
              <Route path="ragaas-output/:id" element={<RAGASEvaluationOutput/>} />
              <Route path="chatbot/:id" element={<ChatbotDetail />} />
              <Route path="datastore/:id" element={<DatastoreConfigDetail />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
