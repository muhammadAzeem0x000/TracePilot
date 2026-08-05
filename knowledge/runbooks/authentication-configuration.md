# Authentication Configuration Checks

Authentication failures after deployment commonly come from issuer, audience, callback URL, clock,
or signing-key configuration rather than password validation. Compare the active environment values
with the intended deployment manifest without copying secrets into incident notes.

For widespread `invalid_audience` or `invalid_issuer` errors, inspect decoded non-sensitive token
claims and the API verifier configuration. For intermittent signature failures, confirm key rotation
propagated to every instance and that the JWKS cache can refresh. A callback mismatch usually affects
only browser sign-in and should be checked against the exact scheme, host, path, and environment.

Never disable signature or audience verification as an incident workaround. Restore the last known
good configuration or deploy the corrected value, then verify login, refresh, and one authorized API
request.
