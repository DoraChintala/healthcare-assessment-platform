# Validation performed

Validated on 3 October 2026.

| Check | Result |
| --- | --- |
| Python workflow/API/provider/retrieval tests | 15 passed |
| Java authentication tests | 3 passed |
| Java gateway compilation and executable jar | Gradle test and bootJar passed |
| Angular production build | Passed |
| Angular TypeScript check | Passed |
| Live Java -> FastAPI -> worker integration | Submission, clarification, resume, approval, unauthorized denial and viewer denial passed |
| Persistent workflow recovery | SQLite checkpoint closed/reopened and resumed in tests |
| Qdrant filtering behavior | In-memory Qdrant client isolation test passed |
| Compose YAML and dependency structure | Validated |
| Worker metrics | Live endpoint contained workflow-node timings |
| Five-profile HTTP benchmark | Executed against mock extraction/local retrieval/SQLite |
| Five-record exact-value evaluation | Executed in mock mode; parsing smoke baseline only |

The integration checks used real application processes, not mocked gateway responses. A five-profile mock benchmark demonstrated that the script runs; its timing results are not representative production capacity measurements.

Not exercised here: Docker image builds or the full PostgreSQL/Qdrant Compose stack (Docker was unavailable), PostgreSQL checkpoint restart behavior, external LLM inference, AWS deployment and cloud billing. Compatible-provider transport was tested using mocked HTTP responses. PostgreSQL and Qdrant configuration is included for local Docker execution; validate that route on your machine before using it as deployment evidence.

Browser screenshot/interaction checks could not execute because the environment denied a socket operation required by Chromium. The Angular build and type checks passed, the dev server served the app during integration, and the complete review API path was tested. Visual rendering and browser interactions still need verification on a local browser.

Suggested local verification:

1. Run `docker compose up --build`.
2. Complete both the Requirements met and Missing license examples in the UI.
3. Restart the worker while an assessment awaits clarification and resume it afterward.
4. Confirm a viewer token cannot approve or correct assessments.
5. Configure an actual model provider and repeat grounding/adversarial evaluation with representative labeled inputs.
