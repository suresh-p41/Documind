import json
import logging
import threading
from dataclasses import asdict

from app import review_rules
from app.db import get_connection
from app.services.llm_service import extract_information, verify_extraction
from app.services.pdf_service import extract_pdf

log = logging.getLogger("documind.worker")

_wake = threading.Event()
_stop = threading.Event()


def notify() -> None:
    """Wake the worker immediately (called after a new batch is created)."""
    _wake.set()


def _claim_next(conn):
    """Take the oldest queued file and mark it as processing."""
    with conn:
        row = conn.execute(
            "SELECT id, filename, stored_path FROM files "
            "WHERE status = 'queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE files SET status = 'processing', error = NULL, "
            "started_at = datetime('now'), finished_at = NULL WHERE id = ?",
            (row["id"],),
        )
    return row


def _process(conn, row) -> None:
    log.info("Processing file %s (%s)", row["id"], row["filename"])
    try:
        pdf = extract_pdf(row["stored_path"])
        result = extract_information(pdf.text)
        signals = verify_extraction(pdf.text, result)
        reasons = review_rules.evaluate(
            result.model_dump(), signals.model_dump() if signals else None, pdf
        )
    except Exception as exc:
        log.exception("File %s failed", row["id"])
        with conn:
            conn.execute(
                "UPDATE files SET status = 'failed', error = ?, "
                "finished_at = datetime('now') WHERE id = ?",
                (str(exc) or type(exc).__name__, row["id"]),
            )
        return

    # Keep the OCR quality numbers for the dashboard; the text itself isn't needed
    ocr_quality = {k: v for k, v in asdict(pdf).items() if k != "text"}

    with conn:
        conn.execute(
            "UPDATE files SET status = 'completed', result_json = ?, ocr_quality = ?, review_signals = ?, "
            "review_status = ?, review_reasons = ?, review_note = NULL, reviewed_at = NULL, "
            "finished_at = datetime('now') WHERE id = ?",
            (
                result.model_dump_json(),
                json.dumps(ocr_quality),
                signals.model_dump_json() if signals else None,
                "needs_review" if reasons else "none",
                json.dumps(reasons) if reasons else None,
                row["id"],
            ),
        )
    log.info(
        "File %s completed%s", row["id"],
        f" - needs review ({len(reasons)} reason(s))" if reasons else "",
    )


def _run() -> None:
    conn = get_connection()
    try:
        while not _stop.is_set():
            row = _claim_next(conn)
            if row is None:
                # Nothing to do: sleep until notified, re-check every 5s anyway
                _wake.wait(timeout=5)
                _wake.clear()
                continue
            _process(conn, row)
    finally:
        conn.close()


def start() -> None:
    # A file left as 'processing' means the server stopped mid-file
    # (crash, Ctrl+C or --reload). Put it back in the queue.
    conn = get_connection()
    with conn:
        reset = conn.execute(
            "UPDATE files SET status = 'queued', started_at = NULL "
            "WHERE status = 'processing'"
        ).rowcount
    conn.close()
    if reset:
        log.info("Re-queued %s interrupted file(s)", reset)

    _stop.clear()
    threading.Thread(target=_run, name="documind-worker", daemon=True).start()
    log.info("Worker started")


def stop() -> None:
    _stop.set()
    _wake.set()
