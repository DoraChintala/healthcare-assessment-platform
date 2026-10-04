# AWS deployment blueprint

Docker Compose is the implemented local deployment. No AWS resources are provisioned by this repository.

Use these mappings when extending the starter:

| Local component | AWS option |
| --- | --- |
| Angular static build | S3 and CloudFront |
| Java gateway and Python API | ECS/Fargate services behind an ALB |
| Single Python worker | Separate ECS/Fargate service |
| PostgreSQL | RDS PostgreSQL on a private network |
| Qdrant | Managed Qdrant or a properly operated private service |
| Hosted model inference | Configured managed provider adapter |
| Secrets | Secrets Manager |
| Logs, alarms, dashboards | CloudWatch and OpenTelemetry integration |

Fargate is appropriate for these application containers; self-hosted GPU inference requires a GPU-capable service such as an EC2-backed deployment. Right-size it through measured workload tests rather than selecting hardware by model parameter count alone.

Before exposing the demo publicly, replace demo tokens with JWT validation and server-derived tenant/role claims, configure TLS and private service connectivity, limit request rates and input sizes, add migrations, and design data retention. Database resume storage can later be replaced with encrypted object storage plus short-lived authorized reads.

Move from the database queue to SQS only when needed. Commit the assessment and a transactional outbox record together; publish the outbox to SQS; fence graph invocations per assessment; handle redelivery without repeating decisions. Add worker concurrency only after these guarantees are tested.

An initial cost experiment should compare one application-worker replica against demand, then vary model size, context length and output token limits while holding the labeled dataset fixed. Separate queue delay, model latency and human waiting time. This repository intentionally does not claim model compression, GPU optimization or production cloud deployment has been performed.
