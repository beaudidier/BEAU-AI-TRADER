import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import { GuestRoute, ProtectedRoute } from "./auth/ProtectedRoute";
import BacktestingPage from "./pages/BacktestingPage";
import BillingPage from "./pages/BillingPage";
import Dashboard from "./pages/Dashboard";
import EvidencePage from "./pages/EvidencePage";
import ProfileSettingsPage from "./pages/ProfileSettingsPage";
import PaperTradingPage from "./pages/PaperTradingPage";
import LearningPage from "./pages/LearningPage";
import TradeWorkspacePage from "./pages/TradeWorkspacePage";
import ValidationPage from "./pages/ValidationPage";
import ForwardValidationPage from "./pages/ForwardValidationPage";
import LatestSignalsPage from "./pages/LatestSignalsPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import type { AppPage } from "./components/Sidebar";

function ProtectedApplication() {
  const routerNavigate = useNavigate();
  const location = useLocation();
  const [dashboardSearch, setDashboardSearch] = useState("");
  const workspaceMatch = location.pathname.match(/^\/workspace\/([A-Za-z0-9.-]+)$/);
  const page: AppPage = location.pathname === "/backtesting" ? "backtesting" : location.pathname === "/paper-trading" ? "paper-trading" : location.pathname === "/forward-validation" ? "forward-validation" : location.pathname === "/latest-signals" ? "latest-signals" : location.pathname === "/learning" ? "learning" : location.pathname === "/validation" ? "validation" : location.pathname === "/evidence" ? "evidence" : "dashboard";

  function navigatePage(nextPage: AppPage) {
    routerNavigate(nextPage === "dashboard" ? "/dashboard" : nextPage === "backtesting" ? "/backtesting" : nextPage === "paper-trading" ? "/paper-trading" : nextPage === "forward-validation" ? "/forward-validation" : nextPage === "latest-signals" ? "/latest-signals" : nextPage === "learning" ? "/learning" : nextPage === "validation" ? "/validation" : "/evidence");
  }

  if (workspaceMatch) {
    return <TradeWorkspacePage ticker={workspaceMatch[1].toUpperCase()} onBack={() => routerNavigate("/dashboard")} onNavigate={navigatePage} />;
  }

  if (page === "backtesting") {
    return <BacktestingPage onNavigate={navigatePage} />;
  }

  if (page === "paper-trading") {
    return <PaperTradingPage onNavigate={navigatePage} />;
  }

  if (page === "forward-validation") {
    return <ForwardValidationPage onNavigate={navigatePage} />;
  }

  if (page === "latest-signals") {
    return <LatestSignalsPage onNavigate={navigatePage} />;
  }

  if (page === "learning") {
    return <LearningPage onNavigate={navigatePage} />;
  }

  if (page === "evidence") return <EvidencePage onNavigate={navigatePage} />;

  if (page === "validation") return <ValidationPage onNavigate={navigatePage} />;

  return <Dashboard searchTerm={dashboardSearch} onSearchChange={setDashboardSearch} onOpenChart={(stock) => routerNavigate(`/workspace/${stock.ticker}`)} onNavigate={navigatePage} />;
}

function App() {
  return <BrowserRouter><AuthProvider><Routes><Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} /><Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} /><Route path="/forgot-password" element={<GuestRoute><ForgotPasswordPage /></GuestRoute>} /><Route path="/reset-password" element={<GuestRoute><ResetPasswordPage /></GuestRoute>} /><Route path="/settings/profile" element={<ProtectedRoute><ProfileSettingsPage /></ProtectedRoute>} /><Route path="/settings/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} /><Route path="/dashboard" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/backtesting" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/paper-trading" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/forward-validation" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/latest-signals" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/learning" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/validation" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/evidence" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/workspace/:ticker" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/chart" element={<Navigate to="/dashboard" replace />} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></AuthProvider></BrowserRouter>;
}

export default App;
