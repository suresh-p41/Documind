import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api.js";
import JsonTree from "../components/JsonTree.jsx";
import ReviewPanel from "../components/ReviewPanel.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDateTime, formatDuration } from "../format.js";
import { usePolling } from "../usePolling.js";

const RUNNING = new Set(["queued", "processing"]);

function OcrQuality({ ocr }) {
  if (!ocr) return null;
  const pct = (v) => (v == null ? "n/a" : `${Math.round(v * 100)}%`);
  const problems = ocr.low_quality_pages.length > 0 || ocr.empty_pages.length > 0;
  return (
    <p className={`ocr-line ${problems ? "ocr-bad" : ""}`}>
      OCR confidence {pct(ocr.ocr_score)} · lowest page {pct(ocr.min_page_ocr_score)} · {ocr.page_count} page
      {ocr.page_count === 1 ? "" : "s"}
      {ocr.low_quality_pages.length > 0 && ` · low-quality pages: ${ocr.low_quality_pages.join(", ")}`}
      {ocr.empty_pages.length > 0 && ` · empty pages: ${ocr.empty_pages.join(", ")}`}
    </p>
  );
}

function ReprocessButton({ file, onDone }) {
  const [busy, setBusy] = useState(false);
  if (RUNNING.has(file.status)) return null;

  async function reprocess() {
    const warning =
      file.review_status === "approved" || file.review_status === "rejected"
        ? "This file has already been reviewed. Reprocessing replaces the JSON and clears the review decision. Continue?"
        : "Run OCR and extraction again for this file? The current JSON will be replaced.";
    if (!window.confirm(warning)) return;
    setBusy(true);
    try {
      await api.reprocessFile(file.id);
      onDone();
    } catch (err) {
      window.alert(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button className="secondary" disabled={busy} onClick={reprocess}>
      {busy ? "Queuing…" : "Reprocess"}
    </button>
  );
}

function JsonPanel({ file }) {
  const [view, setView] = useState("tree");
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(file.result, null, 2);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function download() {
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.filename.replace(/\.pdf$/i, "") + ".json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="card panel">
      <div className="panel-header">
        <h2>Extracted JSON</h2>
        <div className="toolbar">
          <div className="segmented">
            <button className={view === "tree" ? "active" : ""} onClick={() => setView("tree")}>Tree</button>
            <button className={view === "raw" ? "active" : ""} onClick={() => setView("raw")}>Raw</button>
          </div>
          <button className="secondary" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
          <button className="secondary" onClick={download}>Download</button>
        </div>
      </div>
      <div className="panel-body">
        {view === "tree" ? <JsonTree data={file.result} /> : <pre className="json-raw">{text}</pre>}
      </div>
    </section>
  );
}

export default function FilePage() {
  const { fileId } = useParams();
  const { data: file, error, reload } = usePolling(
    () => api.getFile(fileId),
    2000,
    (f) => f === null || RUNNING.has(f.status)
  );

  if (error && !file) return <p className="error">Could not load file: {error}</p>;
  if (!file) return <p className="muted">Loading…</p>;

  return (
    <div>
      <p className="breadcrumb">
        <Link to="/">All batches</Link> / <Link to={`/batches/${file.batch_id}`}>#{file.batch_id} {file.batch_name}</Link>
      </p>

      <div className="page-header">
        <div>
          <h1>{file.filename}</h1>
          <p className="muted">
            Started {formatDateTime(file.started_at)}
            {file.finished_at && ` · Took ${formatDuration(file.started_at, file.finished_at)}`}
          </p>
          <OcrQuality ocr={file.ocr_quality} />
        </div>
        <div className="badges">
          <StatusBadge status={file.status} />
          <StatusBadge status={file.review_status} />
          <ReprocessButton file={file} onDone={reload} />
        </div>
      </div>

      {file.error && <div className="card alert-bad"><strong>Processing failed:</strong> {file.error}</div>}

      <ReviewPanel key={`${file.id}-${file.review_status}`} file={file} onChange={reload} />

      <div className="split">
        {file.result ? (
          <JsonPanel file={file} />
        ) : (
          <section className="card panel">
            <h2>Extracted JSON</h2>
            <p className="muted">
              {RUNNING.has(file.status) ? "Not ready yet — this page updates automatically." : "No JSON was produced for this file."}
            </p>
          </section>
        )}

        <section className="card panel">
          <div className="panel-header">
            <h2>Original document</h2>
            <a href={api.pdfUrl(file.id)} target="_blank" rel="noreferrer">Open in new tab</a>
          </div>
          <iframe className="pdf-frame" src={api.pdfUrl(file.id)} title={file.filename} />
        </section>
      </div>
    </div>
  );
}
