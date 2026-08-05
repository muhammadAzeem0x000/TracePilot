# External API Timeout Response

Use this procedure when a payment, identity, messaging, or storage dependency begins timing out.
Separate connect timeouts from read timeouts and rate-limit responses. Check dependency latency,
TracePilot request duration, retry counts, and circuit-breaker state before increasing any timeout.

Retries must have exponential backoff, jitter, and a strict attempt cap. A request that creates a
remote object needs an idempotency key; otherwise retries can create duplicate charges or messages.
If the dependency is degraded, shed optional work and return a bounded failure instead of allowing
requests to occupy every worker.

Capture the provider request identifier, status or exception class, timeout phase, and customer
impact. Coordinate with the provider using those identifiers, not API keys or payload secrets.
