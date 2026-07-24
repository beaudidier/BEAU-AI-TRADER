import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import { GuestRoute, ProtectedRoute } from "./auth/ProtectedRoute";
import ChartPage from "./pages/ChartPage";
import BacktestingPage from "./pages/BacktestingPage";
import BillingPage from "./pages/BillingPage";
import Dashboard from "./pages/Dashboard";
import ProfileSettingsPage from "./pages/ProfileSettingsPage";
import PaperTradingPage from "./pages/PaperTradingPage";
import LearningPage from "./pages/LearningPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import type { AppPage } from "./components/Sidebar";
import type { Stock } from "./types/stock";

function ProtectedApplication() {
  const routerNavigate = useNavigate();
  const location = useLocation();
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const page: AppPage = location.pathname === "/backtesting" ? "backtesting" : location.pathname === "/paper-trading" ? "paper-trading" : location.pathname === "/learning" ? "learning" : "dashboard";

  function navigatePage(nextPage: AppPage) {
    setSelectedStock(null);
    routerNavigate(nextPage === "dashboard" ? "/dashboard" : nextPage === "backtesting" ? "/backtesting" : nextPage === "paper-trading" ? "/paper-trading" : "/learning");
  }

  if (selectedStock) {
    return <ChartPage stock={selectedStock} onBack={() => { setSelectedStock(null); routerNavigate("/dashboard"); }} onNavigate={navigatePage} />;
  }

  if (page === "backtesting") {
    return <BacktestingPage onNavigate={navigatePage} />;
  }

  if (page === "paper-trading") {
    return <PaperTradingPage onNavigate={navigatePage} />;
  }

  if (page === "learning") {
    return <LearningPage onNavigate={navigatePage} />;
  }

  return <Dashboard onOpenChart={(stock) => { setSelectedStock(stock); routerNavigate("/chart"); }} onNavigate={navigatePage} />;
}

function App() {
  return <BrowserRouter><AuthProvider><Routes><Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} /><Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} /><Route path="/forgot-password" element={<GuestRoute><ForgotPasswordPage /></GuestRoute>} /><Route path="/reset-password" element={<GuestRoute><ResetPasswordPage /></GuestRoute>} /><Route path="/settings/profile" element={<ProtectedRoute><ProfileSettingsPage /></ProtectedRoute>} /><Route path="/settings/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} /><Route path="/dashboard" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/backtesting" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/paper-trading" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/learning" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="/chart" element={<ProtectedRoute><ProtectedApplication /></ProtectedRoute>} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></AuthProvider></BrowserRouter>;
}

export default App;
