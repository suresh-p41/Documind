# DocuMind

**Turn scanned US legal documents into structured JSON, and know which results need a human check.**

DocuMind reads scanned or digital PDFs (contracts, leases, deeds, court orders, IRS notices),
extracts the key facts into JSON, and automatically routes uncertain results to a
human verification queue. Everything runs locally: no document ever leaves the machine.

## Features

- **Batch processing:** upload many PDFs at once; a background worker processes them one by one.
- **Live progress:** see each batch and each file move from queued → processing → completed / failed.
- **Structured JSON:** parties and roles, dates, amounts, governing law, court details, clauses,
  identifiers, signatures, notarization, plus masked sensitive data (SSNs show only the last 4 digits).
- **Human verification:** reviewers approve or reject results; any file can be sent to review manually.
- **Automatic review rules:** documents are flagged when something looks wrong (see below).
- **Side-by-side view:** extracted JSON next to the original PDF.

## How it works

```
 PDF ──► OCR (Docling + RapidOCR) ──► Extraction (LLM) ──► Verification pass (LLM) ──► Review rules
          text + per-page OCR score     JSON matching the     compares JSON with the       needs_review?
                                        schema                document, quotes evidence
```

| Layer | Technology |
|---|---|
| OCR | [Docling](https://github.com/docling-project/docling) with RapidOCR, full-page mode |
| LLM | [Ollama](https://ollama.com) running `qwen2.5:7b` locally, structured JSON output |
| Backend | FastAPI, SQLite, background worker thread |
| Frontend | React 18 + Vite |

### Automatic verification rules

A file goes to the verification queue when any of these fire:

| Rule | Triggered by |
|---|---|
| Document type | Type is unknown, or the verifier is guessing |
| Entity ambiguity | No parties found, or several organizations with no clear primary party |
| Missing required fields | Per-type business rules, e.g. a deed needs a notary, a court order needs a case number |
| Identifier uncertainty | EIN not in XX-XXXXXXX format, unlabelled or unreadable identifiers |
| OCR quality | Page OCR confidence below 85%, empty pages, garbled text |
| Conflicting information | The same fact with two different values (e.g. two rent amounts) |
| Suspicious content | Embedded instructions aimed at an AI, signs of tampering |

Issues reported by the LLM verifier must quote the document; quotes that don't actually
appear in the text are discarded, which filters out invented problems.
The required-field rules live in a table at the top of [`backend/app/review_rules.py`](backend/app/review_rules.py).

## Getting started

### Prerequisites

- macOS, Linux or Windows with **16 GB RAM** or more
- Python 3.12, Node.js 20
- [Ollama](https://ollama.com/download)

### 1. Download the model

```bash
ollama pull qwen2.5:7b
```

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --reload --reload-dir app --port 8000
```

The first run downloads the OCR models. API docs: http://localhost:8000/docs

### 3. Frontend (in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where the backend reaches Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Model used for extraction and verification |
| `STATIC_DIR` | unset | Container only: folder with the built dashboard to serve |

Local development needs none of them set as long as Ollama runs on its default port.

### Validate

Lint, type-check and frontend build, the same checks CI runs on every push and PR:

```bash
pip install ruff mypy
scripts/validate.sh
```

See [`AGENTS.md`](AGENTS.md) for the repo guide for coding agents.

### Command-line alternative

To process a folder without the dashboard (writes one JSON file per PDF to `backend/output/`):

```bash
cd backend
.venv/bin/python main.py path/to/pdfs
```

### Deploy to Kubernetes

The repo-root `Dockerfile` builds one image (API + dashboard) listening on port 8080.
`deploy/` runs Ollama as a second pod in the same namespace, reachable only through
an internal `ClusterIP` Service (`http://ollama:11434`), so documents still never leave
your own infrastructure. The model is set once in `deploy/config.yaml`.

In the cluster the model is `qwen2.5:3b`, not `qwen2.5:7b`: the hackathon team quota
allows 4 CPU / 8Gi of requests per namespace and at most 2 CPU / 4Gi per container,
and 7b needs more than 4Gi. The manifests request 2 CPU / 4.5Gi in total
(Ollama 1500m / 3Gi, app 500m / 1.5Gi), and each container is limited to 2 CPU / 4Gi.
If 3b is too slow or runs out of memory, set `qwen2.5:1.5b` in `deploy/config.yaml`.

```bash
docker build -t <YOUR_REGISTRY>/documind:<TAG> . && docker push <YOUR_REGISTRY>/documind:<TAG>
# set the image in deploy/documind.yaml, then:
kubectl apply -k deploy/ -n <YOUR_TEAM_NAMESPACE>
```

The app reads `OLLAMA_BASE_URL` (default `http://localhost:11434`) and `OLLAMA_MODEL`
(default `qwen2.5:7b`), so local development needs no changes; `deploy/config.yaml`
sets `qwen2.5:3b` for the cluster.

## Try it

Sample documents are in [`testdata/`](testdata/):

- `testdata/cuad_scanned/`: real US contracts as realistic scans
- `testdata/synthetic/`: documents with planted problems that should be flagged
- `testdata/irs_notices/`: official IRS sample notices

Upload `cuad_scanned/` and `synthetic/` together as one batch to see OCR, extraction,
flagged files and a failed file in one run. [`testdata/README.md`](testdata/README.md)
lists the expected result for each file.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/batches` | Upload PDFs (multipart `files`, optional `name`) and start a batch |
| `GET` | `/api/batches` | List batches with progress counts |
| `GET` | `/api/batches/{id}` | One batch with every file's status |
| `GET` | `/api/files/{id}` | One file: status, review info, OCR quality, extracted JSON |
| `GET` | `/api/files/{id}/pdf` | The original PDF |
| `POST` | `/api/files/{id}/review` | `{"action": "flag" \| "approve" \| "reject", "note": "..."}` |
| `POST` | `/api/files/{id}/reprocess` | Run a file again |
| `GET` | `/api/review-queue` | Files by review status (`needs_review`, `approved`, `rejected`) |

## Project structure

```
backend/
  app/
    api.py              FastAPI endpoints
    worker.py           Background processing queue
    db.py               SQLite schema and migrations
    schemas.py          JSON output schema (Pydantic)
    review_rules.py     Automatic verification rules
    services/
      pdf_service.py    OCR and OCR quality
      llm_service.py    Extraction and verification prompts
  main.py               Command-line batch processor
frontend/
  src/
    pages/              Batches, batch detail, file, verification queue
    components/         Upload form, JSON viewer, review panel, ...
testdata/               Sample documents and expected answers
scripts/validate.sh     Lint + type-check + frontend build (run by CI)
.github/workflows/      CI
```

## Known limitations

- Documents longer than about 10 pages are rejected (`Document too long`); chunking is next on the roadmap.
- Reviewers can approve or reject results but not edit the JSON.
- No user accounts or authentication; intended to run on a trusted machine.
- Tested mainly on synthetic documents and short CUAD contracts; accuracy on real scanned filings still needs measuring.
- The LLM verifier is not perfectly consistent between runs; the code-based rules are the reliable part.

## Data and licenses

- CUAD contracts in `testdata/`: [The Atticus Project](https://www.atticusprojectai.org/cuad), CC BY 4.0.
- IRS sample notices: US government works, public domain.
- Synthetic documents: created for this project; all names and numbers are fictitious.
