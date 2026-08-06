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
| Average tool calls | 4.43 |
| Average latency | 10335.0 ms |
| Average confidence | 0.607 |
| Confidence when correct | 0.607 |
| Confidence when incorrect | n/a |
| High-confidence incorrect | 0 |
| Average input tokens | 5902.714 |
| Average output tokens | 831.000 |
| Average total tokens | 6733.714 |
| Average estimated cost USD | n/a |
| Scenarios using fallback | 0 |
| Completed / failed | 7 / 0 |

## Scenario results

| Scenario | Completed | Correct | Citation P/R | Confidence | Tools | Latency ms | Tokens | Fallback | Failure class |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| holdout_webhook_timeout_regression | True | True | 1.00/1.00 | 0.600 | 4 | 9873.9 | 6500 | False | — |
| holdout_tenant_cache_scope | True | True | 1.00/1.00 | 0.600 | 5 | 10280.5 | 6420 | False | — |
| holdout_oauth_secret_newline | True | True | 1.00/1.00 | 0.550 | 4 | 9448.7 | 6235 | False | — |
| holdout_job_ack_before_effect | True | True | 1.00/1.00 | 0.600 | 4 | 9144.3 | 6208 | False | — |
| holdout_blue_green_stale_config | True | True | 1.00/1.00 | 0.600 | 5 | 9716.4 | 6319 | False | — |
| holdout_replica_schema_drift | True | True | 1.00/1.00 | 0.600 | 4 | 9052.7 | 6128 | False | — |
| holdout_checkout_pool_starvation | True | True | 1.00/1.00 | 0.700 | 5 | 14828.5 | 9326 | False | — |

## Preserved details

### holdout_webhook_timeout_regression

- Expected: `tracepilot/holdout-fixtures@a101010101010101010101010101010101010101`
- Predicted: `tracepilot/holdout-fixtures@a101010101010101010101010101010101010101`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/holdout-fixtures@a101010101010101010101010101010101010101, knowledge/runbooks/external-api-timeouts.md#holdout-1
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5741 / 759 / 6500
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_tenant_cache_scope

- Expected: `tracepilot/holdout-fixtures#611`
- Predicted: `tracepilot/holdout-fixtures#611`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request, get_pull_request_files
- Cited sources: tracepilot/holdout-fixtures#611, knowledge/architecture/tenant-authorization.md#holdout-2
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5554 / 866 / 6420
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_oauth_secret_newline

- Expected: `tracepilot/holdout-fixtures@b201010101010101010101010101010101010101`
- Predicted: `tracepilot/holdout-fixtures@b201010101010101010101010101010101010101`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/holdout-fixtures@b201010101010101010101010101010101010101, knowledge/runbooks/authentication-configuration.md#holdout-3
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5477 / 758 / 6235
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_job_ack_before_effect

- Expected: `tracepilot/holdout-fixtures@c301010101010101010101010101010101010101`
- Predicted: `tracepilot/holdout-fixtures@c301010101010101010101010101010101010101`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/holdout-fixtures@c301010101010101010101010101010101010101, knowledge/architecture/job-execution.md#holdout-4
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5463 / 745 / 6208
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_blue_green_stale_config

- Expected: `tracepilot/holdout-fixtures#623`
- Predicted: `tracepilot/holdout-fixtures#623`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request, get_pull_request_files
- Cited sources: tracepilot/holdout-fixtures#623, knowledge/runbooks/deployment-rollback.md#holdout-5
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5554 / 765 / 6319
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_replica_schema_drift

- Expected: `tracepilot/holdout-fixtures@d401010101010101010101010101010101010101`
- Predicted: `tracepilot/holdout-fixtures@d401010101010101010101010101010101010101`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_commit
- Cited sources: tracepilot/holdout-fixtures@d401010101010101010101010101010101010101, knowledge/runbooks/database-migrations.md#holdout-6
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 5441 / 687 / 6128
- Estimated cost USD: None
- Fallback: False; reasons: none

### holdout_checkout_pool_starvation

- Expected: `tracepilot/holdout-fixtures#637`
- Predicted: `tracepilot/holdout-fixtures#637`
- Called tools: list_recent_commits, list_recent_pull_requests, search_knowledge, get_pull_request, get_pull_request_files
- Cited sources: tracepilot/holdout-fixtures#637, knowledge/architecture/checkout-service.md#holdout-7
- Failure: none
- Provider/model: deepseek / deepseek-v4-flash
- Token usage (input/output/total): 8089 / 1237 / 9326
- Estimated cost USD: None
- Fallback: False; reasons: none
