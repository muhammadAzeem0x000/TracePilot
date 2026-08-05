# Deployment Rollback Procedure

Rollback is appropriate when a newly deployed application revision causes broad errors and a safe
forward fix is not immediately available. Confirm the incident start time aligns with the release,
identify the last known-good immutable image, and verify whether the new release also changed the
database schema or asynchronous job payloads.

Pause progressive rollout before changing traffic. If the database change is backward compatible,
route traffic to the previous image and monitor error rate, latency, checkout success, and queue
depth. Never reverse a destructive database migration merely because application traffic moved
back; use a reviewed forward repair.

After rollback, compare configuration and feature flags because an image rollback alone does not
restore environment variables. Preserve logs and deployment metadata. Declare recovery only after
the primary customer transaction and one dependent background workflow succeed.
