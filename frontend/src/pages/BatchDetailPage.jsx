import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api.js";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime, formatDuration } from "../format.js";
import { usePolling } from "../usePolling.js";

const RUNNING = new Set(["queued", "processing"]);

function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function BatchDetailPage() {
  const { batchId } = useParams();
  const navigate = useNavigate();

  // Poll every 2s, but only while something is still queued or processing.
  // `active` is re-evaluated on every render, so polling stops by itself
  // once the batch finishes.
  const { data: batch, error } = usePolling(
    () => api.getBatch(batchId),
    2000,
    (b) => b === null || RUNNING.has(b.status)
  );

  if (error && !batch) return <p className="error">Could not load batch: {error}</p>;
  if (!batch) return <p className="muted">Loading…</p>;

  const { counts } = batch;
  const running = RUNNING.has(batch.status);

  return (
    <div>
      <p className="breadcrumb"><Link to="/">← All batches</Link></p>

      <div className="page-header">
        <div>
          <h1>#{batch.id} {batch.name}</h1>
          <p className="muted">
            Created {formatDateTime(batch.created_at)}
            {batch.finished_at && ` · Finished ${formatDateTime(batch.finished_at)}`}
            {running && " · Updating live"}
          </p>
        </div>
        <StatusBadge status={batch.status} />
      </div>

      <section className="card">
        <div className="stats">
          <Stat label="Total" value={counts.total} />
          <Stat label="Queued" value={counts.queued} />
          <Stat label="Processing" value={counts.processing} tone={counts.processing ? "info" : null} />
          <Stat label="Completed" value={counts.completed} tone="ok" />
          <Stat label="Failed" value={counts.failed} tone={counts.failed ? "bad" : null} />
          <Stat label="Needs review" value={counts.needs_review} tone={counts.needs_review ? "warn" : null} />
        </div>
        <ProgressBar counts={counts} />
        <p className="muted small">{batch.progress_percent}% done</p>
      </section>

      <section className="card">
        <h2>Files</h2>
        <table className="table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>Review</th>
              <th>Time taken</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {batch.files.map((f) => (
              <tr key={f.id} className="clickable" onClick={() => navigate(`/files/${f.id}`)}>
                <td>
                  <Link to={`/files/${f.id}`} onClick={(e) => e.stopPropagation()}>{f.filename}</Link>
                </td>
                <td><StatusBadge status={f.status} /></td>
                <td>
                  {f.review_status === "none"
                    ? <span className="muted">—</span>
                    : <StatusBadge status={f.review_status} />}
                </td>
                <td className="muted">
                  {f.status === "queued" ? "Waiting" : formatDuration(f.started_at, f.finished_at)}
                </td>
                <td className="details-cell">
                  {f.error && <span className="error-text">{f.error}</span>}
                  {!f.error && f.has_result && <span className="muted">JSON ready</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
