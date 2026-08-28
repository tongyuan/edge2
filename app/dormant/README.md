# Dormant diagnostics

The MRZ Robustness report is intentionally not exposed by the EDGE 2.0
application. Its report engine remains covered by unit tests, and its frontend
assets are retained here so the diagnostic can be reinstated deliberately in a
future change.

Do not move these assets into `app/static` or register their page/API routes
without an explicit decision to expose the report again.
