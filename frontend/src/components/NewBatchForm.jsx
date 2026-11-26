import { useRef, useState } from "react";

import { api } from "../api.js";
import { formatBytes } from "../format.js";

export default function NewBatchForm({ onCreated }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  function addFiles(list) {
    const incoming = Array.from(list);
    const pdfs = incoming.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const skipped = incoming.length - pdfs.length;
    setError(skipped ? `${skipped} non-PDF file(s) skipped` : null);
    // Ignore files already in the list (same name and size)
    setFiles((current) => {
      const seen = new Set(current.map((f) => `${f.name}:${f.size}`));
      return [...current, ...pdfs.filter((f) => !seen.has(`${f.name}:${f.size}`))];
    });
  }

  function removeFile(index) {
    setFiles((current) => current.filter((_, i) => i !== index));
  }

  async function submit(event) {
    event.preventDefault();
    if (!files.length) return;
    setSubmitting(true);
    setError(null);
    try {
      const batch = await api.createBatch(name.trim(), files);
      setName("");
      setFiles([]);
      onCreated(batch);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card new-batch" onSubmit={submit}>
      <h2>Start a new batch</h2>

      <label className="field">
        <span>Batch name (optional)</span>
        <input
          type="text"
          value={name}
          placeholder="e.g. Client X – November leases"
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
      >
        <strong>Drop PDF files here</strong> or click to choose
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }}
        />
      </div>

      {files.length > 0 && (
        <ul className="file-list">
          {files.map((file, i) => (
            <li key={`${file.name}:${file.size}`}>
              <span>{file.name}</span>
              <span className="muted">{formatBytes(file.size)}</span>
              <button type="button" className="link-button" onClick={() => removeFile(i)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="error">{error}</p>}

      <button type="submit" className="primary" disabled={!files.length || submitting}>
        {submitting
          ? "Uploading…"
          : `Start processing${files.length ? ` ${files.length} file${files.length > 1 ? "s" : ""}` : ""}`}
      </button>
    </form>
  );
}
