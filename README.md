# Brain OS Enterprise Workflow Platform

An invoice-approval workflow platform: raw invoice text goes in, a
LangGraph state machine extracts the structured fields, scores risk,
auto-approves or pauses for a human, and produces an executive
briefing -- with every step persisted to SQLite for a full audit trail.

## Architecture

```
app/
  api/         FastAPI routes (/brain-os/start, /resume, /status, /audit)
               + bearer-token auth dependency (security.py)
  workflows/   LangGraph state machine: extract -> risk -> approval_gate -> briefing
  services/    Business logic: document intelligence, risk engine,
               executive briefing (Anthropic), Slack notifications
  database/    SQLite schema/repository (Facility 3: Knowledge Memory)
               + ChromaDB vector memory for duplicate detection
  models/      Pydantic schemas shared across the API and workflow
  utils/       Settings (pydantic-settings) and logging
tests/         pytest suite (34 tests) against a real FastAPI TestClient
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

## Authentication

Every `/brain-os/*` endpoint requires an `Authorization: Bearer <token>`
header. The expected token comes from the `BRAIN_OS_API_TOKEN`
environment variable, read through the same `Settings` object as every
other config value (`app/utils/config.py`) -- there is no separate auth
config system.

**This is required, not optional.** Unlike `ANTHROPIC_API_KEY` or
`SLACK_BOT_TOKEN`, which degrade gracefully to a fallback behavior when
unset, an unset or blank `BRAIN_OS_API_TOKEN` makes every `/brain-os/*`
request fail with `401` -- there is no "auth disabled" mode. This is
deliberate: it's not possible to accidentally deploy with the API wide
open by forgetting to set a token.

`GET /health` is the one exception: it stays public with no token
required, because container orchestrators (Docker, Kubernetes, ECS)
need to reach it without credentials to run liveness/readiness checks.

Swagger UI at `/docs` shows this requirement and has an "Authorize"
button for testing with a token interactively; the bearer scheme is
declared in the OpenAPI schema itself (`components.securitySchemes`),
never with a real token value baked in.

**Locally**: copy `.env.example` to `.env` and replace the placeholder
with a real value (e.g. `openssl rand -hex 32`):

```bash
cp .env.example .env
# edit .env: BRAIN_OS_API_TOKEN=<your generated value>
```

**In any shared or deployed environment**: set `BRAIN_OS_API_TOKEN`
through your platform's secret manager (see Deployment path below) --
never commit a real value. `.env` is git-ignored and docker-ignored for
exactly this reason.

## Running locally

The project already has a virtualenv at `.venv` with all dependencies
installed. To set it up from scratch elsewhere:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # required: set a real BRAIN_OS_API_TOKEN; optionally add ANTHROPIC_API_KEY / SLACK_BOT_TOKEN
```

Start the server:

```bash
.venv/bin/uvicorn app.main:app --reload
```

SQLite databases and the Chroma index are created automatically on
first startup under `data/`. Visit `http://127.0.0.1:8000/docs` for
interactive API docs.

### Example session

The examples below use `change-me-in-production` as a stand-in for
whatever real value you set `BRAIN_OS_API_TOKEN` to -- **never use that
literal placeholder outside local development.**

```bash
AUTH="Authorization: Bearer change-me-in-production"

# Small invoice -- auto-approved immediately
curl -X POST http://127.0.0.1:8000/brain-os/start \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"text": "Vendor: Small Co\nPO Number: PO-1\nAmount: $100"}'

# Large invoice -- pauses for approval
curl -X POST http://127.0.0.1:8000/brain-os/start \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"text": "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500"}'
# -> {"workflow_id": "wf-...", "status": "awaiting_approval", ...}

# Resume it
curl -X POST http://127.0.0.1:8000/brain-os/resume \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"workflow_id": "wf-...", "decision": "approved", "user": "alice"}'

# Check status or audit trail at any point
curl -H "$AUTH" http://127.0.0.1:8000/brain-os/status/wf-...
curl -H "$AUTH" http://127.0.0.1:8000/brain-os/audit/wf-...

# /health needs no Authorization header
curl http://127.0.0.1:8000/health
```

Omitting `-H "$AUTH"`, or passing the wrong token, returns `401` with a
generic `{"detail": "Missing or invalid bearer token."}` body -- the
response never reveals what the correct token is or which part of the
request was wrong.

## Testing

```bash
.venv/bin/pytest -v
```

34 tests cover: invoice submission and field extraction, auto-approve
vs. pause-for-review risk scoring, duplicate-invoice detection, the
pause/resume checkpoint cycle (including double-resume and
resume-on-already-completed-workflow error cases), the audit trail
recorded for both auto-approved and human-decided workflows, the
`/health` liveness probe, and bearer-token authentication (missing
token, invalid token, valid token, an unconfigured token failing
closed, `/health` staying public, and the OpenAPI schema correctly
declaring the bearer requirement). Each test runs against an isolated
SQLite/Chroma/checkpoint stack under pytest's `tmp_path`, driven through
a real FastAPI `TestClient` authenticated with a test-only token that
never touches the environment or any `.env` file
(`tests/conftest.py::TEST_API_TOKEN`).

## Running with Docker

```bash
cp .env.example .env               # required: set a real BRAIN_OS_API_TOKEN; optionally add ANTHROPIC_API_KEY / SLACK_BOT_TOKEN
docker compose up -d --build       # or: make up
curl http://localhost:8000/health                                          # public, no token needed
curl -H "Authorization: Bearer <your BRAIN_OS_API_TOKEN>" \
  http://localhost:8000/brain-os/status/wf-does-not-exist                  # 404, not 401 -- proves the token worked
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
3. **Secrets**: set `BRAIN_OS_API_TOKEN` (required -- see Authentication
   above), and optionally `ANTHROPIC_API_KEY` and `SLACK_BOT_TOKEN` /
   `SLACK_APPROVAL_CHANNEL`, via the platform's secret manager (AWS Secrets
   Manager, GCP Secret Manager, Kubernetes Secrets, ...) injected as
   environment variables -- never a committed `.env` (see `.dockerignore`,
   which keeps `.env` out of the image entirely). Rotate `BRAIN_OS_API_TOKEN`
   the same way you'd rotate any bearer credential; there is currently no
   in-app rotation/expiry mechanism (see Known limitations).
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
   gateway for **TLS termination** (the app itself speaks plain HTTP;
   application-layer auth via `BRAIN_OS_API_TOKEN` is not a substitute
   for TLS on the wire) and point Slack's outbound webhook or your own
   scheduler at `POST /brain-os/start`, with the bearer token attached,
   for automated intake.

## Known limitations

- **Single-writer storage.** SQLite and the local Chroma index are fine
  for an MVP and moderate local load, but are not built for multiple
  concurrent app replicas (see Deployment path above for the fix).
- **Regex-based extraction.** The document intelligence parser expects
  the `Vendor: / PO Number: / Amount:` line format from the spec. Free-form
  or scanned/OCR'd invoices would need a real extraction model (the
  Anthropic client is already wired in via `ExecutiveBriefingService` and
  could be extended to do extraction too).
- **Auth is a single shared bearer token, not per-user identity.** Every
  caller uses the same `BRAIN_OS_API_TOKEN` -- there's no per-user
  identity, no roles/scopes (e.g. "can submit invoices" vs. "can
  approve"), and no token rotation/expiry mechanism. `human_in_loop`
  audit rows still record whatever free-text `user` the caller supplies
  in the request body, which the token does not verify. This is
  sufficient to keep the API from being wide open to the internet, not
  a full authz system -- add OAuth2/OIDC with real user identity before
  this needs to distinguish who is allowed to approve what.
- **No rate limiting.** The auth layer stops unauthenticated access, not
  a valid-token caller hammering the API; add rate limiting at the
  gateway or in-app before launch.
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
