const LABELS = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  completed_with_errors: "Completed with errors",
  failed: "Failed",
  needs_review: "Needs review",
  approved: "Approved",
  rejected: "Rejected",
};

const TONES = {
  queued: "neutral",
  processing: "info",
  completed: "ok",
  completed_with_errors: "warn",
  failed: "bad",
  needs_review: "warn",
  approved: "ok",
  rejected: "bad",
};

export default function StatusBadge({ status }) {
  if (!status || status === "none") return null;
  return (
    <span className={`badge badge-${TONES[status] || "neutral"}`}>
      {status === "processing" && <span className="spinner" aria-hidden="true" />}
      {LABELS[status] || status}
    </span>
  );
}
