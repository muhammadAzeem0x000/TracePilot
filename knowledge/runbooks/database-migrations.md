# Database Migration Verification

Use this runbook when application code expects a table, column, enum value, or index that is
missing in the production database. Typical symptoms include `UndefinedColumn`, failed inserts,
checkout HTTP 500 responses immediately after deploy, and errors naming fields such as
`payment_status` or `checkout_session_id`.

First compare the application release SHA with the migration version recorded in production. Check
that every migration expected by the release appears in the migration ledger and that the database
schema contains the referenced object. Do not repeatedly restart application instances: a schema
mismatch is deterministic and restarts do not repair it.

If a forward migration was omitted, stop further rollout and apply the reviewed migration through
the normal migration mechanism. Prefer completing the missing forward change over manually editing
tables. If the migration is unsafe or incompatible, roll the application back to the last release
whose schema contract matches production. Verify checkout creation and one read path after recovery.

Record the release SHA, missing migration identifier, database object, affected endpoints, and the
exact recovery action in the incident timeline. Before closing, add a deployment gate that compares
the expected and applied migration heads.
