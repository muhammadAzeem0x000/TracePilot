# TracePilot Incident Evaluation

Prompt: `investigation_v2`  
Model: `deepseek-chat`  
Confidence is model-reported and is not a calibrated probability.

## Aggregate metrics

| Metric | Result |
| --- | ---: |
| Completion rate | 1.000 |
| Culprit accuracy | 1.000 |
| Citation precision | 1.000 |
| Citation recall | 1.000 |
| Invalid citation rate | 0.000 |
| Average tool calls | 4.20 |
| Average latency | 7896.5 ms |
| Average confidence | 0.615 |
| Confidence when correct | 0.615 |
| Confidence when incorrect | n/a |
| High-confidence incorrect | 0 |
| Completed / failed | 10 / 0 |

## Scenario results

| Scenario | Completed | Correct | Citation P/R | Confidence | Tools | Latency ms | Failure class |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| checkout_schema_gap | True | True | 1.00/1.00 | 0.600 | 4 | 9025.4 | — |
| refund_duplicate_execution | True | True | 1.00/1.00 | 0.600 | 4 | 7730.6 | — |
| catalog_latency_fanout | True | True | 1.00/1.00 | 0.600 | 4 | 7792.2 | — |
| auth_environment_mismatch | True | True | 1.00/1.00 | 0.550 | 5 | 8374.1 | — |
| payment_retry_storm | True | True | 1.00/1.00 | 0.700 | 4 | 8429.3 | — |
| tenant_scope_regression | True | True | 1.00/1.00 | 0.700 | 4 | 9064.5 | — |
| deployment_port_regression | True | True | 1.00/1.00 | 0.600 | 4 | 6681.2 | — |
| attachment_limit_regression | True | True | 1.00/1.00 | 0.600 | 5 | 7769.5 | — |
| rate_limit_window_mismatch | True | True | 1.00/1.00 | 0.600 | 4 | 7804.5 | — |
| stale_search_endpoint | True | True | 1.00/1.00 | 0.600 | 4 | 6293.6 | — |

## Preserved details

### checkout_schema_gap

- Expected: `tracepilot/evaluation-fixtures@1111111111111111111111111111111111111111`
- Predicted: `tracepilot/evaluation-fixtures@1111111111111111111111111111111111111111`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@1111111111111111111111111111111111111111, knowledge/runbooks/database-migrations.md#chunk-eval-1
- Failure: none

### refund_duplicate_execution

- Expected: `tracepilot/evaluation-fixtures@2222222222222222222222222222222222222222`
- Predicted: `tracepilot/evaluation-fixtures@2222222222222222222222222222222222222222`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@2222222222222222222222222222222222222222, knowledge/past_incidents/duplicate-refund-jobs.md#chunk-eval-2
- Failure: none

### catalog_latency_fanout

- Expected: `tracepilot/evaluation-fixtures#303`
- Predicted: `tracepilot/evaluation-fixtures#303`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request_files
- Cited sources: tracepilot/evaluation-fixtures#303, knowledge/past_incidents/catalog-n-plus-one.md#chunk-eval-3
- Failure: none

### auth_environment_mismatch

- Expected: `tracepilot/evaluation-fixtures@4444444444444444444444444444444444444444`
- Predicted: `tracepilot/evaluation-fixtures@4444444444444444444444444444444444444444`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit, search_knowledge
- Cited sources: tracepilot/evaluation-fixtures@4444444444444444444444444444444444444444, knowledge/runbooks/authentication-configuration.md#chunk-eval-4, knowledge/runbooks/authentication-configuration.md#chunk-eval-4
- Failure: none

### payment_retry_storm

- Expected: `tracepilot/evaluation-fixtures#505`
- Predicted: `tracepilot/evaluation-fixtures#505`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request_files
- Cited sources: tracepilot/evaluation-fixtures#505, knowledge/runbooks/external-api-timeouts.md#chunk-eval-5
- Failure: none

### tenant_scope_regression

- Expected: `tracepilot/evaluation-fixtures@6666666666666666666666666666666666666666`
- Predicted: `tracepilot/evaluation-fixtures@6666666666666666666666666666666666666666`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@6666666666666666666666666666666666666666, knowledge/architecture/tenant-authorization.md#chunk-eval-6
- Failure: none

### deployment_port_regression

- Expected: `tracepilot/evaluation-fixtures@7777777777777777777777777777777777777777`
- Predicted: `tracepilot/evaluation-fixtures@7777777777777777777777777777777777777777`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@7777777777777777777777777777777777777777, knowledge/runbooks/deployment-rollback.md#chunk-eval-7
- Failure: none

### attachment_limit_regression

- Expected: `tracepilot/evaluation-fixtures#808`
- Predicted: `tracepilot/evaluation-fixtures#808`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request, get_pull_request_files
- Cited sources: tracepilot/evaluation-fixtures#808, knowledge/architecture/upload-validation.md#chunk-eval-8
- Failure: none

### rate_limit_window_mismatch

- Expected: `tracepilot/evaluation-fixtures@9999999999999999999999999999999999999999`
- Predicted: `tracepilot/evaluation-fixtures@9999999999999999999999999999999999999999`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@9999999999999999999999999999999999999999, knowledge/runbooks/rate-limits.md#chunk-eval-9
- Failure: none

### stale_search_endpoint

- Expected: `tracepilot/evaluation-fixtures@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- Predicted: `tracepilot/evaluation-fixtures@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/evaluation-fixtures@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, knowledge/past_incidents/stale-environment-value.md#chunk-eval-10
- Failure: none
