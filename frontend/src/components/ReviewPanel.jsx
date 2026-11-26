import { useState } from "react";

import { api } from "../api.js";
import { formatDateTime } from "../format.js";
import ReviewReasons from "./ReviewReasons.jsx";
import StatusBadge from "./StatusBadge.jsx";

// Human verification controls for one file.
//   none                -> "Send to verification" (with optional reason)
//   needs_review        -> reasons + Approve / Reject (reject needs a note)
//   approved / rejected -> outcome + "Send back to verification"
export default function ReviewPanel({ file, onChange }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Only finished files can be verified
  if (file.status !== "completed" && file.status !== "failed") return null;

  async function act(action) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.reviewFile(file.id, action, note);
      setNote("");
      onChange(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const status = file.review_status;

  return (
    <section className={`card review-panel review-${status}`}>
      <div className="panel-header">
        <h2>Human verification</h2>
        <StatusBadge status={status} />
      </div>

      {status !== "none" && (
        <>
          <p className="muted small">Why it was sent to verification:</p>
          <ReviewReasons reasons={file.review_reasons} />
        </>
      )}

      {(status === "approved" || status === "rejected") && (
        <p className="review-outcome">
          <strong>{status === "approved" ? "Approved" : "Rejected"}</strong> on {formatDateTime(file.reviewed_at)}
          {file.review_note && <> — “{file.review_note}”</>}
        </p>
      )}

      <label className="field">
        <span>
          {status === "needs_review"
            ? "Reviewer note (required to reject)"
            : "Reason for verification (optional)"}
        </span>
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="toolbar">
        {status === "needs_review" ? (
          <>
            <button className="success" disabled={busy} onClick={() => act("approve")}>Approve</button>
            <button className="danger" disabled={busy || !note.trim()} onClick={() => act("reject")}>Reject</button>
          </>
        ) : (
          <button className="secondary" disabled={busy} onClick={() => act("flag")}>
            {status === "none" ? "Send to verification" : "Send back to verification"}
          </button>
        )}
      </div>
    </section>
  );
}
