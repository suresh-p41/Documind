// Stacked bar: completed (green) + failed (red) + processing (blue) out of total
export default function ProgressBar({ counts }) {
  const { total, completed, failed, processing } = counts;
  if (!total) return null;
  const pct = (n) => `${(100 * n) / total}%`;
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={completed + failed}
      title={`${completed} completed, ${failed} failed, ${processing} processing, ${counts.queued} queued`}
    >
      <div className="progress-ok" style={{ width: pct(completed) }} />
      <div className="progress-bad" style={{ width: pct(failed) }} />
      <div className="progress-info" style={{ width: pct(processing) }} />
    </div>
  );
}
