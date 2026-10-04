# API contract

Public requests go through the gateway at `/api`. Authentication is the local demo bearer token. The gateway derives tenant, actor and role from its account mapping; browser-supplied tenant headers are ignored.

| Method | Path | Result |
| --- | --- | --- |
| GET | /api/jobs | Accessible demo jobs |
| GET | /api/samples | Synthetic resume examples |
| GET | /api/assessments | Most recent 100 tenant-scoped records |
| POST | /api/assessments | 202 plus assessment ID and queued state |
| GET | /api/assessments/{id} | Status, version, evidence and result |
| GET | /api/assessments/{id}/audit | Ordered intake, worker and reviewer events |
| POST | /api/assessments/{id}/review | Correction/resume or final reviewer decision |

Create body:

```json
{"job_id":"rn-icu","resume_text":"Experience: 5 years\nLicense: DEMO-VA-1001\nState: VA"}
```

`Idempotency-Key` is required, 1-100 alphanumeric/hyphen characters. Requests accept only known schema fields. Resume text is limited to 30,000 characters. `job_id` is `rn-icu` or `rn-general` in the demo.

Clarification body (use the current version returned by GET):

```json
{"action":"clarify","notes":"Confirmed synthetic credential evidence","corrections":{"license_number":"DEMO-VA-1001"},"expected_version":2}
```

Supported correction fields: `years_experience`, `license_number`, `license_state`. The service validates types and ranges before queuing a command. Corrections apply only while awaiting clarification. Unresolved corrections may pause the graph again.

Final decision body:

```json
{"action":"approve","notes":"Reviewed the rule results and supporting evidence","expected_version":5}
```

`reject` records an override of the recommendation; it is not a candidate rejection. Final decisions require `AWAITING_APPROVAL`. A stale version or repeated completed decision returns 409. Viewers receive 403 on review. Cross-tenant record access returns 404. Missing or invalid credentials return 401.

The AI service is internal in Compose. `/docs` exposes its generated OpenAPI interface during local development, but calling its protected endpoints requires internal service credentials and trusted identity context.
