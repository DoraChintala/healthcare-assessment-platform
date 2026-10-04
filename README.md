# Healthcare Candidate Assessment Platform

A runnable portfolio starter for Full Stack AI and Java engineering. It combines Angular, a Spring Boot gateway, a Python/FastAPI API, a persistent LangGraph workflow, qualification rules, filtered Qdrant retrieval, and human review.

**Use synthetic records only. The registry is simulated and this application does not verify real nursing credentials or make hiring decisions.**

## Run with Docker Compose

Prerequisite: Docker Desktop or Docker Engine with Compose v2. No host Java, Python or Node installation is needed for this route.

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:4200. Connect with `local-demo-reviewer-token` (or the value you configured in `.env`). `local-demo-viewer-token` can submit and inspect assessments but cannot review them.

The browser calls the Java gateway through the UI proxy. PostgreSQL and Qdrant are not published to host ports. Application ports bind to localhost. PostgreSQL data and graph checkpoints survive a restart in the `postgres-data` volume; Qdrant policy data uses `qdrant-data`.

```bash
docker compose logs -f worker
docker compose down
```

The normal `down` command preserves volumes. Do not remove volumes when testing checkpoint recovery.

## Try the complete workflow

1. Connect to the demo.
2. Choose the Requirements met sample and create an assessment. It moves from Queued to Awaiting approval. Inspect rule results, evidence quotes and policies. Enter reviewer notes and approve the recommendation.
3. Choose the Missing license sample. It pauses in Awaiting clarification. Enter `DEMO-VA-1001` as the corrected license and explain the evidence in reviewer notes. Save and resume. The existing assessment continues and moves to Awaiting approval.
4. Try the Expired license sample. The recommendation is Requirements not met. The UI never converts this into an automatic rejection or hiring action.
5. Try the Prompt injection probe. The mock parser ignores the injected instruction and the expired license still fails. This is a mock-path regression test, not proof that a real LLM is immune to injection.

Approval accepts a recommendation; override records disagreement with it. Both require reviewer notes and an unchanged record version. All workflow and review events appear in the audit trail.

## What is implemented

| Area | Implementation |
| --- | --- |
| Frontend | Angular 19 candidate intake, status polling, evidence viewer, corrections, approval and audit |
| Java | Spring Boot 3.4 / Java 17 gateway, Gradle build, bounded HTTP calls, local demo roles |
| Python | FastAPI typed endpoints, input validation, tenant-scoped reads and review permissions |
| Processing | Database-backed leased queue, heartbeat, bounded retries, stale-owner result protection |
| Workflow | LangGraph extraction, retrieval, rule evaluation, summary and persistent clarification interrupt |
| Persistence | PostgreSQL in Compose; SQLite for lightweight development and tests |
| Extraction | Deterministic mock parser by default; configurable compatible LLM endpoint |
| Retrieval | Qdrant vectors with tenant/job filters; lightweight local fallback |
| Evidence | Resume quotations, reviewer corrections, versioned policy records and simulated registry results |
| Evaluation | Exact-value extraction smoke evaluation, workflow tests and HTTP latency/throughput script |

This starter uses a fixed workflow, hashed demo embeddings and deterministic grounded summaries. A real semantic encoder, hybrid retrieval/reranking and model-generated narratives are deliberate extension points. There is no autonomous agent planner, PDF/DOCX parser, real registry adapter, object-storage integration or deployed AWS infrastructure in this version.

## Local development without Docker

Prerequisites: Python 3.12, Java 17 and Node 22. Use Node 22 for this Angular 19 starter.

Terminal 1:

```bash
cd ai-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
uvicorn app.main:app --port 8000
```

Terminal 2, from the same directory with the same virtual environment:

```bash
source .venv/bin/activate
python -m app.worker
```

Both processes use the same `ai-service/var` directory by default. SQLite checkpoint storage is durable. Local retrieval does not need a Qdrant server.

Terminal 3:

```bash
cd gateway
./gradlew bootRun
```

Terminal 4:

```bash
cd ui
npm ci
npm start
```

Open http://localhost:4200. On Windows use `gradlew.bat` and the Windows virtual-environment activation command.

## Configure a real LLM

The provider adapter uses a server-side compatible `/v1/chat/completions` endpoint supporting JSON output. It can connect to a suitable hosted provider or a locally served model. It has no tool-execution permissions.

For Compose, change `.env`:

```dotenv
LLM_MODE=compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-actual-model-name
LLM_API_KEY=your-server-side-key
INPUT_USD_PER_MILLION=your_actual_input_rate
OUTPUT_USD_PER_MILLION=your_actual_output_rate
```

Use numeric rates, not the placeholder words shown above. Keep keys out of git and the browser. Recreate the AI services after changing the configuration:

```bash
docker compose up -d --force-recreate ai-api worker
```

For local development, export the same variables in the worker terminal before starting it. A local model server can use an empty API key if that server permits it. Invalid JSON or unsupported source quotations route to clarification; provider/network failures trigger bounded worker retries.

Reported model cost covers successful extraction calls only. It does not include retry calls, embedding calls, infrastructure or review labor. A zero or unconfigured cost is not a claim that real inference is free.

## Run checks and evaluations

```bash
cd ai-service
source .venv/bin/activate
pytest -q
PYTHONPATH=. python ../scripts/evaluate.py
```

```bash
cd gateway
./gradlew test bootJar
```

```bash
cd ui
npm ci
npm run build
npm run typecheck
```

Against a running Java gateway:

```bash
python scripts/benchmark.py --profiles 20 --concurrency 4
```

The benchmark measures submission-to-ready-for-review latency, including queue delay and polling granularity. It excludes human waiting time. It creates real synthetic assessment records in your local demo database.

The five-record evaluation is a parsing and workflow smoke baseline. Build a larger labeled train/validation/test corpus before making accuracy claims. Run the same counterfactual and adversarial cases against each real provider configuration.

## API examples

```bash
curl http://localhost:8080/api/assessments \
  -H 'Authorization: Bearer local-demo-reviewer-token'
```

```bash
curl -X POST http://localhost:8080/api/assessments \
  -H 'Authorization: Bearer local-demo-reviewer-token' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-assessment-001' \
  -d '{"job_id":"rn-icu","resume_text":"Experience: 5 years\nLicense: DEMO-VA-1001\nState: VA"}'
```

Repeat the same request with the same idempotency key to receive the same assessment. Reusing the key with different input returns a conflict. API contract: [docs/api.md](docs/api.md).

## Extend toward a production system

Run one worker in this starter. Add graph-invocation fencing before scaling workers. Replace demo authentication with validated OIDC claims before public exposure. Add a real credential-ownership verification adapter, semantic embeddings, a representative evaluation corpus, database migrations, encrypted document storage, observability, retention and a deployment pipeline.

See [architecture and decisions](docs/architecture.md), [AWS deployment blueprint](docs/aws-deployment.md), and [validation results](docs/validation.md) for implemented behavior and boundaries.

Official references: [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [Qdrant filtering](https://qdrant.tech/documentation/search/filtering/), [Spring Boot Gradle plugin](https://docs.spring.io/spring-boot/gradle-plugin/), [Angular CLI](https://angular.dev/tools/cli).
