# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- Planning only: `VISION.md` is Captain-approved and frozen (verify SHA-256 `8ff9483d1c343490d9ab6ee752957ca7ef894853102f101557fed4157b8d8484`; never edit). Implementation stays blocked until every gate in `VALIDATION_RECORD.md` passes with its required evidence; acceptance rules live in `ACCEPTANCE.md`, `DECISION_TABLE.md`, `CONSENT.md`, `DISCOVERY.md`, `LANDED_COST.md`, judgment-layer spec in `JUDGMENT_ENGINE.md` (no live API calls), draft corpus in `FIXTURES.json`.
- V1 build: public skill in `SKILL.md`; deterministic engine in `deal_finder/` (stdlib-only, no network/creds); tests via `python3 -m unittest discover -s tests`; assumptions + captain decision batch in `ASSUMPTIONS.md`.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
