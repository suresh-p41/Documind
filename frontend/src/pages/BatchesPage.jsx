import { Link, useNavigate } from "react-router-dom";

import { api } from "../api.js";
import NewBatchForm from "../components/NewBatchForm.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime } from "../format.js";
import { usePolling } from "../usePolling.js";

export default function BatchesPage() {
  const navigate = useNavigate();
  const { data, error, reload } = usePolling(api.listBatches, 3000);

  const batches = data?.batches ?? [];

  return (
    <div className="batches-page">
      <NewBatchForm
        onCreated={(batch) => {
          reload();
          navigate(`/batches/${batch.batch_id}`);
        }}
      />

      <section className="card">
        <h2>Batches</h2>
        {error && <p className="error">Could not load batches: {error}</p>}
        {data && batches.length === 0 && <p className="muted">No batches yet. Upload PDFs to start one.</p>}

        {batches.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Created</th>
                <th>Status</th>
                <th className="progress-col">Progress</th>
                <th>Needs review</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id} className="clickable" onClick={() => navigate(`/batches/${b.id}`)}>
                  <td>
                    <Link to={`/batches/${b.id}`} onClick={(e) => e.stopPropagation()}>
                      #{b.id} {b.name}
                    </Link>
                  </td>
                  <td className="muted">{formatDateTime(b.created_at)}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td>
                    <ProgressBar counts={b.counts} />
                    <span className="muted small">
                      {b.counts.completed + b.counts.failed} / {b.counts.total} files
                      {b.counts.failed > 0 && ` · ${b.counts.failed} failed`}
                    </span>
                  </td>
                  <td>
                    {b.counts.needs_review > 0
                      ? <StatusBadge status="needs_review" />
                      : <span className="muted">—</span>}
                    {b.counts.needs_review > 0 && <span className="small"> {b.counts.needs_review}</span>}
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
