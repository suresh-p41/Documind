import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api.js";
import ReviewReasons from "../components/ReviewReasons.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime } from "../format.js";
import { usePolling } from "../usePolling.js";

const TABS = [
  { key: "needs_review", label: "Needs review" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

export default function ReviewQueuePage() {
  const [tab, setTab] = useState("needs_review");
  const navigate = useNavigate();
  const { data, error } = usePolling(() => api.reviewQueue(tab), 5000);

  // usePolling keeps the previous tab's data until the next load; hide it
  const files = data?.files?.filter((f) => f.review_status === tab) ?? [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Human verification</h1>
          <p className="muted">Documents that need a person to check the extracted JSON.</p>
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
            {t.label}
            {data && <span className="tab-count">{data.counts[t.key]}</span>}
          </button>
        ))}
      </div>

      <section className="card">
        {error && <p className="error">Could not load queue: {error}</p>}
        {data && files.length === 0 && (
          <p className="muted">
            {tab === "needs_review" ? "Nothing waiting for verification." : "Nothing here yet."}
          </p>
        )}

        {files.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>File</th>
                <th>Batch</th>
                <th>Reasons</th>
                <th>{tab === "needs_review" ? "Processed" : "Decision"}</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id} className="clickable" onClick={() => navigate(`/files/${f.id}`)}>
                  <td>
                    <Link to={`/files/${f.id}`} onClick={(e) => e.stopPropagation()}>{f.filename}</Link>
                    {f.status === "failed" && <> <StatusBadge status="failed" /></>}
                  </td>
                  <td>
                    <Link to={`/batches/${f.batch_id}`} onClick={(e) => e.stopPropagation()}>
                      #{f.batch_id} {f.batch_name}
                    </Link>
                  </td>
                  <td><ReviewReasons reasons={f.review_reasons} /></td>
                  <td className="muted">
                    {tab === "needs_review"
                      ? formatDateTime(f.finished_at)
                      : <>{formatDateTime(f.reviewed_at)}{f.review_note && <div className="small">“{f.review_note}”</div>}</>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
