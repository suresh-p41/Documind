import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { api } from "./api.js";
import BatchDetailPage from "./pages/BatchDetailPage.jsx";
import BatchesPage from "./pages/BatchesPage.jsx";
import FilePage from "./pages/FilePage.jsx";
import ReviewQueuePage from "./pages/ReviewQueuePage.jsx";
import { usePolling } from "./usePolling.js";

function BackendStatus() {
  const [ok, setOk] = useState(null);

  useEffect(() => {
    const check = () => api.health().then(() => setOk(true)).catch(() => setOk(false));
    check();
    const timer = setInterval(check, 10000);
    return () => clearInterval(timer);
  }, []);

  if (ok === null) return null;
  return (
    <span className={`backend-status ${ok ? "ok" : "down"}`}>
      {ok ? "Backend connected" : "Backend offline"}
    </span>
  );
}

function ReviewCount() {
  const { data } = usePolling(() => api.reviewQueue("needs_review"), 10000);
  const count = data?.counts.needs_review ?? 0;
  return count > 0 ? <span className="nav-count">{count}</span> : null;
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand">DocuMind</NavLink>
        <nav>
          <NavLink to="/" end>Batches</NavLink>
          <NavLink to="/review">
            Verification
            <ReviewCount />
          </NavLink>
        </nav>
        <BackendStatus />
      </header>

      <main className="content">
        <Routes>
          <Route path="/" element={<BatchesPage />} />
          <Route path="/batches/:batchId" element={<BatchDetailPage />} />
          <Route path="/files/:fileId" element={<FilePage />} />
          <Route path="/review" element={<ReviewQueuePage />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
