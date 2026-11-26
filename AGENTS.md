# AGENTS.md

Guide for coding agents working in this repo.

## What this is

DocuMind turns scanned or digital US legal PDFs (contracts, leases, deeds, court
orders, IRS notices) into structured JSON and routes uncertain results to a human
review queue. It is **local-only document AI**: documents never leave the server.
OCR runs in-process (Docling + RapidOCR) and the LLM is a local
[Ollama](https://ollama.com) model (`qwen2.5:7b` locally, `qwen2.5:3b` in the cluster).
Never add calls to hosted LLM APIs or other external services that would send
document content off the machine.

## Layout

```
backend/            FastAPI app (Python 3.12)
  app/api.py          HTTP endpoints; also serves the built dashboard when STATIC_DIR is set
  app/worker.py       background processing queue
  app/db.py           SQLite schema and migrations
  app/schemas.py      Pydantic JSON output schema
  app/review_rules.py automatic "needs review" rules (required-field table at the top)
  app/services/       pdf_service.py (OCR + quality), llm_service.py (Ollama prompts)
  main.py             command-line batch processor
frontend/           React 18 + Vite dashboard (plain JS/JSX)
deploy/             Kubernetes manifests (kustomize): app + Ollama pods
testdata/           sample PDFs and expected answers
scripts/validate.sh lint + type-check + frontend build
Dockerfile          one image: API + built dashboard on port 8080
```

## Run locally

Prereqs: Python 3.12, Node.js 20, Ollama running locally.

```bash
ollama pull qwen2.5:7b

# backend (http://localhost:8000, docs at /docs)
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --reload --reload-dir app --port 8000

# frontend, second terminal (http://localhost:5173)
cd frontend && npm install && npm run dev
```

Env vars: `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_MODEL`
(default `qwen2.5:7b`), `STATIC_DIR` (container only: serve the built dashboard).

## Validate

Run before every commit; CI (`.github/workflows/ci.yml`) runs the same script:

```bash
pip install ruff mypy      # lightweight; the heavy runtime deps are not needed
scripts/validate.sh        # SKIP_FRONTEND=1 to skip the frontend build
```

It runs `ruff check .` (config: `ruff.toml`), `mypy` on `backend/`
(config: `mypy.ini`, `ignore_missing_imports = True`) and `npm run build` in
`frontend/`. Fix the code rather than loosening the config; use a targeted
`# noqa: <code>` / `# type: ignore[<code>]` only with a reason.

## Deploy

- `Dockerfile` builds one image (API + dashboard) listening on **port 8080**.
- `deploy/` runs Ollama as a separate pod behind an internal ClusterIP Service
  (`http://ollama:11434`); apply with `kubectl apply -k deploy/ -n <namespace>`.
- The model and Ollama URL are set in `deploy/config.yaml` via `OLLAMA_MODEL` /
  `OLLAMA_BASE_URL`. Team quota: at most 4 CPU / 8Gi per namespace and
  2 CPU / 4Gi per container; keep requests within it.

## Conventions

- Python: type hints on new functions, `X | None` style, line length 120, imports
  sorted (ruff `I`). Keep the backend importable without Ollama running.
- LLM output must match `app/schemas.py`; verifier issues must quote the document.
- Review rules belong in `app/review_rules.py`, as plain code checks where possible.
- Don't commit runtime data (`backend/data/`, `backend/output/`) or secrets (`.env`).
- Keep the README's API table and project structure in sync with code changes.
