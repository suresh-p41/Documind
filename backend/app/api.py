import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import worker
from app.db import DATA_DIR, get_connection, init_db

UPLOAD_DIR = DATA_DIR / "uploads"
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB per PDF

# Show DocuMind's own log lines (worker progress) in the server terminal
_log = logging.getLogger("documind")
_log.setLevel(logging.INFO)
if not _log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     [%(name)s] %(message)s"))
    _log.addHandler(_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="DocuMind API", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _validate_pdf(upload: UploadFile) -> None:
    name = upload.filename or ""
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, f"{name or 'File'}: only PDF files are allowed")
    if upload.size is not None and upload.size > MAX_FILE_BYTES:
        raise HTTPException(400, f"{name}: larger than 50 MB")
    header = upload.file.read(5)
    upload.file.seek(0)
    if header != b"%PDF-":
        raise HTTPException(400, f"{name}: not a valid PDF file")


@app.post("/api/batches", status_code=201)
def create_batch(
    files: list[UploadFile] = File(...),
    name: str | None = Form(None),
):
    if not files:
        raise HTTPException(400, "Upload at least one PDF")

    # Check every file before saving anything, so a bad file
    # doesn't leave a half-created batch behind
    for upload in files:
        _validate_pdf(upload)

    batch_name = (name or "").strip() or datetime.now().strftime("Batch %Y-%m-%d %H:%M")

    conn = get_connection()
    batch_dir = None
    try:
        with conn:
            batch_id = conn.execute(
                "INSERT INTO batches (name) VALUES (?)", (batch_name,)
            ).lastrowid

            batch_dir = UPLOAD_DIR / str(batch_id)
            batch_dir.mkdir(parents=True, exist_ok=True)

            created = []
            for index, upload in enumerate(files, start=1):
                # Strip any folder parts from the name; prefix with a number
                # so two uploads called "scan.pdf" don't overwrite each other
                original = Path(upload.filename).name
                stored_path = batch_dir / f"{index:03d}_{original}"
                with stored_path.open("wb") as out:
                    shutil.copyfileobj(upload.file, out)

                file_id = conn.execute(
                    "INSERT INTO files (batch_id, filename, stored_path) VALUES (?, ?, ?)",
                    (batch_id, original, str(stored_path)),
                ).lastrowid
                created.append({"id": file_id, "filename": original, "status": "queued"})
    except Exception:
        # The database rolled back; remove any files already written
        if batch_dir is not None:
            shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    finally:
        conn.close()

    worker.notify()

    return {"batch_id": batch_id, "name": batch_name, "files": created}


# ---------- Batch progress ----------

def _utc(ts: str | None) -> str | None:
    """SQLite stores '2026-11-25 11:32:15' (UTC); send ISO 8601 with Z."""
    return ts.replace(" ", "T") + "Z" if ts else None


def _batch_status(c: dict) -> str:
    if c["queued"] + c["processing"] > 0:
        return "queued" if c["queued"] == c["total"] else "processing"
    if c["failed"] > 0:
        return "completed_with_errors"
    return "completed"


BATCH_SUMMARY_SQL = """
SELECT
    b.id, b.name, b.created_at,
    COUNT(f.id)                                           AS total,
    COALESCE(SUM(f.status = 'queued'), 0)                 AS queued,
    COALESCE(SUM(f.status = 'processing'), 0)             AS processing,
    COALESCE(SUM(f.status = 'completed'), 0)              AS completed,
    COALESCE(SUM(f.status = 'failed'), 0)                 AS failed,
    COALESCE(SUM(f.review_status = 'needs_review'), 0)    AS needs_review,
    MAX(f.finished_at)                                    AS last_finished_at
FROM batches b
LEFT JOIN files f ON f.batch_id = b.id
"""


def _batch_summary(row) -> dict:
    counts = {k: row[k] for k in ("total", "queued", "processing", "completed", "failed", "needs_review")}
    done = counts["completed"] + counts["failed"]
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": _utc(row["created_at"]),
        "status": _batch_status(counts),
        "counts": counts,
        "progress_percent": round(100 * done / counts["total"]) if counts["total"] else 0,
        "finished_at": _utc(row["last_finished_at"]) if done == counts["total"] else None,
    }


@app.get("/api/batches")
def list_batches(limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    conn = get_connection()
    try:
        rows = conn.execute(
            BATCH_SUMMARY_SQL + " GROUP BY b.id ORDER BY b.id DESC LIMIT ? OFFSET ?",
            (limit, max(0, offset)),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    finally:
        conn.close()
    return {"total": total, "batches": [_batch_summary(r) for r in rows]}


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            BATCH_SUMMARY_SQL + " WHERE b.id = ? GROUP BY b.id", (batch_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Batch {batch_id} not found")
        files = conn.execute(
            "SELECT id, filename, status, error, review_status, review_reasons, "
            "created_at, started_at, finished_at, "
            "result_json IS NOT NULL AS has_result "
            "FROM files WHERE batch_id = ? ORDER BY id",
            (batch_id,),
        ).fetchall()
    finally:
        conn.close()

    batch = _batch_summary(row)
    batch["files"] = [
        {
            "id": f["id"],
            "filename": f["filename"],
            "status": f["status"],
            "error": f["error"],
            "review_status": f["review_status"],
            "review_reasons": _reasons(f["review_reasons"]),
            "has_result": bool(f["has_result"]),
            "created_at": _utc(f["created_at"]),
            "started_at": _utc(f["started_at"]),
            "finished_at": _utc(f["finished_at"]),
        }
        for f in files
    ]
    return batch


# ---------- Single file: extracted JSON and original PDF ----------

def _get_file_row(conn, file_id: int):
    row = conn.execute(
        "SELECT f.*, b.name AS batch_name FROM files f "
        "JOIN batches b ON b.id = f.batch_id WHERE f.id = ?",
        (file_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"File {file_id} not found")
    return row


def _reasons(raw: str | None) -> list[dict]:
    return json.loads(raw) if raw else []


def _file_payload(f) -> dict:
    return {
        "id": f["id"],
        "batch_id": f["batch_id"],
        "batch_name": f["batch_name"],
        "filename": f["filename"],
        "status": f["status"],
        "error": f["error"],
        "review_status": f["review_status"],
        "review_reasons": _reasons(f["review_reasons"]),
        "review_note": f["review_note"],
        "reviewed_at": _utc(f["reviewed_at"]),
        "ocr_quality": json.loads(f["ocr_quality"]) if f["ocr_quality"] else None,
        "review_signals": json.loads(f["review_signals"]) if f["review_signals"] else None,
        "created_at": _utc(f["created_at"]),
        "started_at": _utc(f["started_at"]),
        "finished_at": _utc(f["finished_at"]),
        "result": json.loads(f["result_json"]) if f["result_json"] else None,
    }


@app.get("/api/files/{file_id}")
def get_file(file_id: int):
    conn = get_connection()
    try:
        return _file_payload(_get_file_row(conn, file_id))
    finally:
        conn.close()


@app.get("/api/files/{file_id}/pdf")
def get_file_pdf(file_id: int):
    conn = get_connection()
    try:
        f = _get_file_row(conn, file_id)
    finally:
        conn.close()

    path = Path(f["stored_path"]).resolve()
    # Only ever serve files from inside our uploads folder
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.exists():
        raise HTTPException(404, "PDF not available")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f["filename"],
        content_disposition_type="inline",  # open in the browser, don't download
    )


# ---------- Human verification ----------

class ReviewAction(BaseModel):
    # flag:    send to verification (from none, approved or rejected)
    # approve: reviewer accepts the extracted JSON
    # reject:  reviewer says the JSON is wrong / unusable
    action: Literal["flag", "approve", "reject"]
    note: str | None = None


@app.post("/api/files/{file_id}/review")
def review_file(file_id: int, body: ReviewAction):
    note = (body.note or "").strip() or None

    conn = get_connection()
    try:
        with conn:
            f = _get_file_row(conn, file_id)

            if body.action == "flag":
                if f["review_status"] == "needs_review":
                    raise HTTPException(409, "File is already waiting for verification")
                reasons = _reasons(f["review_reasons"])
                reasons.append({
                    "code": "manual",
                    "message": note or "Sent to verification manually",
                    "source": "manual",
                })
                conn.execute(
                    "UPDATE files SET review_status = 'needs_review', review_reasons = ?, "
                    "review_note = NULL, reviewed_at = NULL WHERE id = ?",
                    (json.dumps(reasons), file_id),
                )
            else:
                if f["review_status"] != "needs_review":
                    raise HTTPException(409, "Only files waiting for verification can be approved or rejected")
                if body.action == "reject" and not note:
                    raise HTTPException(400, "Please add a note explaining why the result is rejected")
                conn.execute(
                    "UPDATE files SET review_status = ?, review_note = ?, "
                    "reviewed_at = datetime('now') WHERE id = ?",
                    ("approved" if body.action == "approve" else "rejected", note, file_id),
                )

            return _file_payload(_get_file_row(conn, file_id))
    finally:
        conn.close()


@app.get("/api/review-queue")
def review_queue(status: Literal["needs_review", "approved", "rejected"] = "needs_review"):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT f.id, f.batch_id, b.name AS batch_name, f.filename, f.status, "
            "f.review_status, f.review_reasons, f.review_note, f.reviewed_at, f.finished_at "
            "FROM files f JOIN batches b ON b.id = f.batch_id "
            "WHERE f.review_status = ? "
            # Waiting items: oldest first. Decided items: most recent first.
            + ("ORDER BY f.id ASC" if status == "needs_review" else "ORDER BY f.reviewed_at DESC"),
            (status,),
        ).fetchall()
        counts = dict(conn.execute(
            "SELECT review_status, COUNT(*) FROM files "
            "WHERE review_status != 'none' GROUP BY review_status"
        ).fetchall())
    finally:
        conn.close()

    return {
        "counts": {s: counts.get(s, 0) for s in ("needs_review", "approved", "rejected")},
        "files": [
            {
                "id": r["id"],
                "batch_id": r["batch_id"],
                "batch_name": r["batch_name"],
                "filename": r["filename"],
                "status": r["status"],
                "review_status": r["review_status"],
                "review_reasons": _reasons(r["review_reasons"]),
                "review_note": r["review_note"],
                "reviewed_at": _utc(r["reviewed_at"]),
                "finished_at": _utc(r["finished_at"]),
            }
            for r in rows
        ],
    }


@app.post("/api/files/{file_id}/reprocess")
def reprocess_file(file_id: int):
    """Put a finished file back in the queue (e.g. after rules or the prompt change)."""
    conn = get_connection()
    try:
        with conn:
            f = _get_file_row(conn, file_id)
            if f["status"] in ("queued", "processing"):
                raise HTTPException(409, "File is already queued or processing")
            conn.execute(
                "UPDATE files SET status = 'queued', error = NULL, result_json = NULL, "
                "ocr_quality = NULL, review_signals = NULL, review_status = 'none', review_reasons = NULL, "
                "review_note = NULL, reviewed_at = NULL, started_at = NULL, finished_at = NULL "
                "WHERE id = ?",
                (file_id,),
            )
            payload = _file_payload(_get_file_row(conn, file_id))
    finally:
        conn.close()
    worker.notify()
    return payload


# In the container image the built React dashboard is served by this same
# app on one port (see Dockerfile). Local dev is unchanged: STATIC_DIR is
# unset there and Vite serves the frontend.
STATIC_DIR = os.getenv("STATIC_DIR")
if STATIC_DIR and Path(STATIC_DIR).is_dir():
    app.mount("/assets", StaticFiles(directory=Path(STATIC_DIR) / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (Path(STATIC_DIR) / path).resolve()
        if path and file.is_file() and file.is_relative_to(Path(STATIC_DIR).resolve()):
            return FileResponse(file)
        return FileResponse(Path(STATIC_DIR) / "index.html")
