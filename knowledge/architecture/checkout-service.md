# Checkout Service Architecture

The fictional checkout service accepts a cart, creates a checkout session, reserves inventory, and
requests a payment authorization. The synchronous HTTP path writes `checkout_sessions` and an
outbox event in one PostgreSQL transaction. A worker later consumes the outbox event and finalizes
inventory and customer notification.

The API owns validation and idempotency. Payment requests use the checkout session UUID as the
provider idempotency key. The database status lifecycle is `created`, `payment_pending`, `paid`,
`failed`, and `expired`. Application code must remain compatible with the production migration head;
adding a status or column requires a forward migration before code begins writing it.

Customer-facing success depends on the database, inventory service, and payment provider. Email and
analytics are asynchronous and must not turn a successful payment into an HTTP 500 response.
