import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/Layout";
import Chat from "./pages/Chat";
import Writer from "./pages/Writer";
import Reader from "./pages/Reader";
import Outputs from "./pages/Outputs";
import Settings from "./pages/Settings";
import Research from "./pages/Research";

import "./index.css";
document.body.className = "bg-slate-50 text-slate-900 antialiased";

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/chat" element={<Chat />} />
          <Route path="/writer" element={<Writer />} />
          <Route path="/reader" element={<Reader />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/outputs" element={<Outputs />} />
          <Route path="/research" element={<Research />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
