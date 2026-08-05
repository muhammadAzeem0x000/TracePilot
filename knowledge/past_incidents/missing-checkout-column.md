# Past Incident: Checkout Column Missing After Release

Checkout returned HTTP 500 for all new sessions for eleven minutes. The deployed application began
writing `payment_status`, but the production migration job had stopped before applying the migration
that added that column. Logs contained PostgreSQL `UndefinedColumn` and named `payment_status`.

The team halted rollout and applied the reviewed forward migration. Error rate returned to baseline
without restarting application instances. Existing sessions were unaffected because reads did not
select the new column until the new code path executed.

The contributing control failure was that application deployment and migration execution were
separate pipelines with no migration-head gate. The follow-up added a pre-traffic check comparing the
release manifest's expected migration with the production ledger.
