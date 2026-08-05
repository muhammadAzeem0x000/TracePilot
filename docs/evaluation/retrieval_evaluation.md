# TracePilot Retrieval Evaluation

Repository scope: `muhammadAzeem0x000/TracePilot`

| Method | Hit@1 | Hit@3 | Hit@5 | MRR | Avg latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| semantic | 0.750 | 1.000 | 1.000 | 0.875 | 2110.8 |
| hybrid | 0.750 | 1.000 | 1.000 | 0.875 | 1934.2 |
| reranked | 0.917 | 1.000 | 1.000 | 0.958 | 4874.1 |

## Per-query results

### semantic

- `checkout code references payment_status but production says the column does not exist` — RR 1.000; top sources: runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, past_incidents/catalog-n-plus-one.md, past_incidents/duplicate-refund-jobs.md
- `new release caused errors and we need the previous image without reversing schema` — RR 1.000; top sources: runbooks/deployment-rollback.md, runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, past_incidents/duplicate-refund-jobs.md, past_incidents/catalog-n-plus-one.md
- `tokens fail with invalid_audience after configuration rollout` — RR 1.000; top sources: runbooks/authentication-configuration.md, past_incidents/missing-checkout-column.md, architecture/tenant-authorization.md, runbooks/database-migrations.md, past_incidents/duplicate-refund-jobs.md
- `payment provider read timeout retries might create duplicate charges` — RR 0.500; top sources: past_incidents/duplicate-refund-jobs.md, runbooks/external-api-timeouts.md, architecture/checkout-service.md, architecture/job-execution.md, past_incidents/catalog-n-plus-one.md
- `where is the checkout outbox event written and which statuses are valid` — RR 1.000; top sources: architecture/checkout-service.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md
- `refund message ran twice after the visibility lease expired` — RR 1.000; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, past_incidents/catalog-n-plus-one.md, runbooks/deployment-rollback.md, architecture/checkout-service.md
- `worker crash redelivers completed work and needs a stable idempotency key` — RR 0.500; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, architecture/checkout-service.md, runbooks/external-api-timeouts.md, past_incidents/missing-checkout-column.md
- `a user can read a record belonging to another organization` — RR 1.000; top sources: architecture/tenant-authorization.md, past_incidents/duplicate-refund-jobs.md, past_incidents/missing-checkout-column.md, past_incidents/catalog-n-plus-one.md, architecture/job-execution.md
- `hundreds of SELECT statements appear while serializing one catalog page` — RR 1.000; top sources: past_incidents/catalog-n-plus-one.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, architecture/job-execution.md, past_incidents/duplicate-refund-jobs.md
- `deployment pipeline needs a gate comparing expected and applied migration heads` — RR 1.000; top sources: past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/deployment-rollback.md, architecture/checkout-service.md, architecture/job-execution.md
- `email analytics failure should not turn a successful payment into HTTP 500` — RR 0.500; top sources: past_incidents/missing-checkout-column.md, architecture/checkout-service.md, past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, runbooks/database-migrations.md
- `rolling back the application did not restore environment variables` — RR 1.000; top sources: runbooks/deployment-rollback.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/authentication-configuration.md, past_incidents/duplicate-refund-jobs.md

### hybrid

- `checkout code references payment_status but production says the column does not exist` — RR 1.000; top sources: runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, past_incidents/catalog-n-plus-one.md, past_incidents/duplicate-refund-jobs.md
- `new release caused errors and we need the previous image without reversing schema` — RR 1.000; top sources: runbooks/deployment-rollback.md, runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, past_incidents/duplicate-refund-jobs.md, past_incidents/catalog-n-plus-one.md
- `tokens fail with invalid_audience after configuration rollout` — RR 1.000; top sources: runbooks/authentication-configuration.md, past_incidents/missing-checkout-column.md, architecture/tenant-authorization.md, runbooks/database-migrations.md, past_incidents/duplicate-refund-jobs.md
- `payment provider read timeout retries might create duplicate charges` — RR 0.500; top sources: past_incidents/duplicate-refund-jobs.md, runbooks/external-api-timeouts.md, architecture/checkout-service.md, architecture/job-execution.md, past_incidents/catalog-n-plus-one.md
- `where is the checkout outbox event written and which statuses are valid` — RR 1.000; top sources: architecture/checkout-service.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md
- `refund message ran twice after the visibility lease expired` — RR 1.000; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, past_incidents/catalog-n-plus-one.md, runbooks/deployment-rollback.md, architecture/checkout-service.md
- `worker crash redelivers completed work and needs a stable idempotency key` — RR 0.500; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, architecture/checkout-service.md, runbooks/external-api-timeouts.md, past_incidents/missing-checkout-column.md
- `a user can read a record belonging to another organization` — RR 1.000; top sources: architecture/tenant-authorization.md, past_incidents/duplicate-refund-jobs.md, past_incidents/missing-checkout-column.md, past_incidents/catalog-n-plus-one.md, architecture/job-execution.md
- `hundreds of SELECT statements appear while serializing one catalog page` — RR 1.000; top sources: past_incidents/catalog-n-plus-one.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, architecture/job-execution.md, past_incidents/duplicate-refund-jobs.md
- `deployment pipeline needs a gate comparing expected and applied migration heads` — RR 1.000; top sources: past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/deployment-rollback.md, architecture/checkout-service.md, architecture/job-execution.md
- `email analytics failure should not turn a successful payment into HTTP 500` — RR 0.500; top sources: past_incidents/missing-checkout-column.md, architecture/checkout-service.md, past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, runbooks/database-migrations.md
- `rolling back the application did not restore environment variables` — RR 1.000; top sources: runbooks/deployment-rollback.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/authentication-configuration.md, past_incidents/duplicate-refund-jobs.md

### reranked

- `checkout code references payment_status but production says the column does not exist` — RR 1.000; top sources: runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, runbooks/deployment-rollback.md, past_incidents/catalog-n-plus-one.md
- `new release caused errors and we need the previous image without reversing schema` — RR 1.000; top sources: runbooks/deployment-rollback.md, runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, architecture/checkout-service.md, architecture/job-execution.md
- `tokens fail with invalid_audience after configuration rollout` — RR 1.000; top sources: runbooks/authentication-configuration.md, runbooks/deployment-rollback.md, runbooks/database-migrations.md, past_incidents/missing-checkout-column.md, runbooks/external-api-timeouts.md
- `payment provider read timeout retries might create duplicate charges` — RR 1.000; top sources: runbooks/external-api-timeouts.md, past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, architecture/checkout-service.md, past_incidents/catalog-n-plus-one.md
- `where is the checkout outbox event written and which statuses are valid` — RR 1.000; top sources: architecture/checkout-service.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/deployment-rollback.md, architecture/job-execution.md
- `refund message ran twice after the visibility lease expired` — RR 1.000; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, runbooks/external-api-timeouts.md, architecture/checkout-service.md, runbooks/deployment-rollback.md
- `worker crash redelivers completed work and needs a stable idempotency key` — RR 0.500; top sources: past_incidents/duplicate-refund-jobs.md, architecture/job-execution.md, architecture/checkout-service.md, runbooks/external-api-timeouts.md, past_incidents/missing-checkout-column.md
- `a user can read a record belonging to another organization` — RR 1.000; top sources: architecture/tenant-authorization.md, runbooks/database-migrations.md, runbooks/authentication-configuration.md, runbooks/external-api-timeouts.md, runbooks/deployment-rollback.md
- `hundreds of SELECT statements appear while serializing one catalog page` — RR 1.000; top sources: past_incidents/catalog-n-plus-one.md, architecture/checkout-service.md, architecture/job-execution.md, past_incidents/duplicate-refund-jobs.md, runbooks/database-migrations.md
- `deployment pipeline needs a gate comparing expected and applied migration heads` — RR 1.000; top sources: past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/deployment-rollback.md, architecture/checkout-service.md, architecture/job-execution.md
- `email analytics failure should not turn a successful payment into HTTP 500` — RR 1.000; top sources: architecture/checkout-service.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/deployment-rollback.md, architecture/job-execution.md
- `rolling back the application did not restore environment variables` — RR 1.000; top sources: runbooks/deployment-rollback.md, past_incidents/missing-checkout-column.md, runbooks/database-migrations.md, runbooks/authentication-configuration.md, past_incidents/duplicate-refund-jobs.md
