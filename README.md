# Brain OS Enterprise Workflow Platform

An invoice-approval workflow platform: raw invoice text goes in, a
LangGraph state machine extracts the structured fields, scores risk,
auto-approves or pauses for a human, and produces an executive
briefing -- with every step persisted to SQLite for a full audit trail.

## Architecture

```
app/
  api/         FastAPI routes (/brain-os/start, /resume, /status, /audit)
  workflows/   LangGraph state machine: extract -> risk -> approval_gate -> briefing
  services/    Business logic: document intelligence, risk engine,
               executive briefing (Anthropic), Slack notifications
  database/    SQLite schema/repository (Facility 3: Knowledge Memory)
               + ChromaDB vector memory for duplicate detection
  models/      Pydantic schemas shared across the API and workflow
  utils/       Settings (pydantic-settings) and logging
tests/         pytest suite (21 tests) against a real FastAPI TestClient
```

### The workflow

1. **Document Intake** (`POST /brain-os/start`) accepts raw invoice text.
2. **Document Intelligence** parses `Vendor:`, `PO Number:`, `Amount:`
   lines into structured fields with a deterministic regex parser (no
   LLM call needed for a fixed key/value format -- fast, free, and
   fully testable).
3. **Knowledge Memory** persists the invoice, and a ChromaDB collection
   (using an offline, dependency-free hashing embedding function --
   no model download required) remembers every invoice seen so far.
4. **Risk Engine** applies the core rule -- amount ≤ $5,000 auto-approves,
   above that pauses for a human -- and layers on anomaly detection
   (missing fields, amounts >10x the threshold, near-duplicate invoices
   found via the vector memory). Any high-severity anomaly forces human
   review even if the raw amount would otherwise auto-approve.
5. **Human in the Loop**: when review is required, the graph calls
   LangGraph's `interrupt()`, which checkpoints the run to SQLite and
   pauses. `POST /brain-os/resume` supplies `approved`/`rejected` and
   resumes the exact same run via `Command(resume=...)` -- the workflow
   is not restarted, it picks up precisely where it paused.
6. **Executive Briefing** generates a final natural-language summary via
   the Anthropic SDK (`ANTHROPIC_API_KEY`); if no key is configured, or
   the call fails, a deterministic template summary is produced instead
   so the endpoint always returns a complete result.
7. **Auditability**: every step above writes a timestamped row to the
   `audit_trail` table, retrievable via `GET /brain-os/audit/{workflow_id}`.

### Why a hashing embedding function instead of a real model?

ChromaDB's default embedding function downloads an ~80MB ONNX model on
first use, which makes the MVP dependent on network access and slow to
start. Brain OS uses a deterministic hashing-trick bag-of-words vectorizer
instead -- it is a real, working ChromaDB collection with real cosine
similarity search, just without a neural embedding model. Swapping in a
different `chromadb.EmbeddingFunction` (e.g. `SentenceTransformerEmbeddingFunction`)
is a one-line change in `app/database/vector_store.py` if higher-fidelity
semantic matching is needed later.

## Running locally

The project already has a virtualenv at `.venv` with all dependencies
installed. To set it up from scratch elsewhere:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: add ANTHROPIC_API_KEY / SLACK_BOT_TOKEN
```

Start the server:

```bash
.venv/bin/uvicorn app.main:app --reload
```

SQLite databases and the Chroma index are created automatically on
first startup under `data/`. Visit `http://127.0.0.1:8000/docs` for
interactive API docs.

### Example session

```bash
# Small invoice -- auto-approved immediately
curl -X POST http://127.0.0.1:8000/brain-os/start \
  -H "Content-Type: application/json" \
  -d '{"text": "Vendor: Small Co\nPO Number: PO-1\nAmount: $100"}'

# Large invoice -- pauses for approval
curl -X POST http://127.0.0.1:8000/brain-os/start \
  -H "Content-Type: application/json" \
  -d '{"text": "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500"}'
# -> {"workflow_id": "wf-...", "status": "awaiting_approval", ...}

# Resume it
curl -X POST http://127.0.0.1:8000/brain-os/resume \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf-...", "decision": "approved", "user": "alice"}'

# Check status or audit trail at any point
curl http://127.0.0.1:8000/brain-os/status/wf-...
curl http://127.0.0.1:8000/brain-os/audit/wf-...
```

## Testing

```bash
.venv/bin/pytest -v
```

21 tests cover: invoice submission and field extraction, auto-approve
vs. pause-for-review risk scoring, duplicate-invoice detection, the
pause/resume checkpoint cycle (including double-resume and
resume-on-already-completed-workflow error cases), the audit trail
recorded for both auto-approved and human-decided workflows, and the
`/health` liveness probe. Each test runs against an isolated
SQLite/Chroma/checkpoint stack under pytest's `tmp_path`, driven through
a real FastAPI `TestClient`.

## Running with Docker

```bash
cp .env.example .env               # optional: add ANTHROPIC_API_KEY / SLACK_BOT_TOKEN
docker compose up -d --build       # or: make up
curl http://localhost:8000/health
```

Invoice data, LangGraph checkpoints, and the Chroma index persist in the
named volume `brain-os-data` (mounted at `/app/data` in the container)
across restarts and rebuilds. `docker compose down` stops the container
without touching that volume; `docker compose down -v` (or `make clean`)
removes it too.

Run the test suite inside a container, built from the Dockerfile's
dedicated `test` stage (the production `runtime` image never ships
`tests/`):

```bash
make test
```

See the [Makefile](Makefile) for the full set of `build`/`up`/`down`/
`logs`/`shell`/`test`/`clean` targets, and
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the scored
readiness assessment and hardening checklist.

## Deployment path

The app is a stateless FastAPI process backed by local files (SQLite +
Chroma), containerized via the `Dockerfile` / `docker-compose.yml` in
this repo. To take it to a cloud environment:

1. **Build and push the image**: `docker build -t <registry>/brain-os:<tag> .`
   then push to your registry (ECR, GCR, ACR, Docker Hub, ...). The image
   runs as a non-root user and exposes a `HEALTHCHECK` on `/health` already.
2. **Persistent storage**: mount a persistent volume/disk at `/app/data`
   (matching the `brain-os-data` volume in `docker-compose.yml`) so
   `brain_os.db`, `checkpoints.db`, and the Chroma index survive restarts
   and redeploys. On Kubernetes this is a `PersistentVolumeClaim`; on
   ECS/Fargate an EFS mount; on a single VM, a mounted disk.
3. **Secrets**: set `ANTHROPIC_API_KEY` and `SLACK_BOT_TOKEN` /
   `SLACK_APPROVAL_CHANNEL` via the platform's secret manager (AWS Secrets
   Manager, GCP Secret Manager, Kubernetes Secrets, ...) injected as
   environment variables -- never a committed `.env` (see `.dockerignore`,
   which keeps `.env` out of the image entirely).
4. **Health checks**: point your orchestrator's liveness/readiness probe
   at `GET /health` (port 8000). It verifies the process is up **and**
   the SQLite store is actually reachable, not just that FastAPI answers.
5. **Scaling beyond a single instance**: SQLite (both the app database
   and the LangGraph checkpointer) assumes a single writer process --
   the image runs `uvicorn --workers 1` deliberately. To run more than
   one replica or worker, swap `SqliteSaver` for `PostgresSaver` (same
   `langgraph-checkpoint` interface) and point the repository layer at a
   shared Postgres database; run ChromaDB as a separate server process
   (`chromadb.HttpClient`) instead of `PersistentClient`. Until that swap
   is made, treat this as a single-instance service in production.
6. Put the service behind your cloud provider's load balancer / API
   gateway (TLS termination, auth) and point Slack's outbound webhook or
   your own scheduler at `POST /brain-os/start` for automated intake.

## Known limitations

- **Single-writer storage.** SQLite and the local Chroma index are fine
  for an MVP and moderate local load, but are not built for multiple
  concurrent app replicas (see Deployment path above for the fix).
- **Regex-based extraction.** The document intelligence parser expects
  the `Vendor: / PO Number: / Amount:` line format from the spec. Free-form
  or scanned/OCR'd invoices would need a real extraction model (the
  Anthropic client is already wired in via `ExecutiveBriefingService` and
  could be extended to do extraction too).
- **No auth.** The API has no authentication/authorization layer; add one
  (API key, OAuth, mTLS) before exposing it outside a trusted network.
- **Vector memory is a fingerprint match, not true semantics.** The
  offline hashing embedding catches near-identical vendor/PO/amount text
  well, but won't catch duplicates phrased very differently.
- **No Slack `/resume` action.** Slack is used one-way (notify only);
  wiring an interactive Slack button to call `POST /brain-os/resume` is a
  natural next step but is out of scope for this MVP.
- **Docker build not yet verified in this environment.** Docker isn't
  installed on the machine this was built on, so the `Dockerfile` /
  `docker-compose.yml` are written to established best practices and
  reviewed carefully, but `docker build` / `docker compose up` should be
  run once by whoever has Docker available before relying on them.

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the full,
scored production-readiness assessment.
