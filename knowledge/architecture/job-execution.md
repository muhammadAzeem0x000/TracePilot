# Background Job Execution Model

Workers use at-least-once delivery. A message can be delivered again after a worker timeout, process
crash, or visibility-lease expiry. Every handler therefore records a stable idempotency key and must
treat an already-completed operation as success.

The job table stores `pending`, `running`, `completed`, and `failed` state with attempt count and
lease expiry. A worker claims a job using a conditional update. Long work renews the lease before
expiry. Two workers must never rely on an in-memory lock for mutual exclusion.

Queue depth alone does not prove duplicate execution. Investigators should compare message IDs,
idempotency keys, lease timestamps, and side-effect identifiers. A handler that sends external
requests must pass the same idempotency key on every retry.
