# Scope 29 — Failure Handling Revalidation

Invalid camera `/dev/video999` produced clean `CAMERA_OPEN_FAILED`, non-zero exit, model not loaded, and actuator disabled. The corrected runner bounds consecutive read failures, releases the camera, rejects invalid frame dimensions before detector/tracker, and does not continue with stale targets. Shape/read-failure injection guards are covered by Scope 29R tests.

The previous Scope 29 failure history is preserved; Scope 29R did not rewrite those runs.
