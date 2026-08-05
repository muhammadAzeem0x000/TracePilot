# Past Incident: Duplicate Refund Job Execution

Several customers received duplicate refund requests after worker processing exceeded the queue
visibility lease. The broker redelivered messages while the first worker was still waiting on the
payment provider. The handler generated a new provider idempotency key on every attempt, so the
provider accepted both requests.

The immediate mitigation paused refund consumers and reconciled provider transaction IDs. The fix
made the refund ID the stable idempotency key and added lease renewal during provider calls. Replayed
messages now detect the completed refund and return success without another side effect.

Queue depth and retry count were normal; the decisive evidence was two worker IDs processing the
same message ID with overlapping lease timestamps.
