# Key-Dependent Validation

Local tests cover deterministic policy, arithmetic, privacy rejection, consent,
and Jev request construction without making network calls. They do not claim
model quality, calibrated thresholds, or any acceptance gate.

The following requires a server-side `TYPESAFE_API_KEY` and the independently
relabelled corpus required by `VALIDATION_RECORD.md`:

- Confirm `jev-1.13.0` accepts the generated Choice/Score/Noul request shape.
- Fit and obtain Captain approval for confidence thresholds and Score weights.
- Produce confidence-versus-accuracy plots and self-consistency measurements.
- Check substitute ordering, including `SUB-A-001` and `SUB-A-002`.
- Re-verify every decisive claim against its source before any `buy` stands.
- Exercise 401, 422, 429, 529, timeout, and outage handling against controlled
  service responses without recording the key.

Until that evidence exists, no acceptance gate should be marked passed. Runtime
service absence and uncertain judgments fail closed to `verify`.
