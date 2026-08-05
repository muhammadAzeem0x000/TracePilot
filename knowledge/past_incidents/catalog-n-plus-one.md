# Past Incident: Catalog N+1 Query Latency

Catalog page latency rose from 180 ms to four seconds after a serializer began loading inventory for
each product separately. Database CPU increased and traces showed hundreds of similar `SELECT`
statements per request. No single query was slow enough to trigger the slow-query threshold.

The team disabled the new serializer field, then replaced per-product lookups with one bounded batch
query. Request query count returned to a constant value and p95 latency recovered. Increasing the
database instance size would have hidden the symptom without correcting request amplification.

The regression test now asserts a query-count ceiling for catalog serialization in addition to
checking response content.
