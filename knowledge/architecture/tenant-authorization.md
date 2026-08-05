# Tenant Authorization Boundary

Every customer-owned record carries `tenant_id`. The API derives the active tenant from verified
identity and membership data; clients cannot choose an arbitrary tenant by adding a request field.
Repository queries require tenant scope as an explicit parameter and database policies provide a
second boundary where supported.

Caching authorization decisions without tenant and membership version in the cache key can leak
access across organizations. Administrative support tools use a separate audited elevation flow and
must not reuse normal customer endpoints with a hidden bypass flag.

Tests should include same-tenant success, cross-tenant denial, removed membership, and identifiers
that exist under another tenant. A `404` can be preferable to `403` when revealing record existence
would itself disclose customer information.
