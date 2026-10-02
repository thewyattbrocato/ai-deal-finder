# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- `VISION.md` is the acceptance policy. A prospective study is required before claiming real shoppers can trust the decision. Acceptance rules live in `ACCEPTANCE.md`, `DECISION_TABLE.md`, `CONSENT.md`, `DISCOVERY.md`, `LANDED_COST.md`, judgment-layer spec in `JUDGMENT_ENGINE.md` (no live API calls), draft corpus in `FIXTURES.json`.
- V1 build: public skill in `SKILL.md`; deterministic engine in `deal_finder/` (stdlib-only, no network/creds); tests via `python3 -m unittest discover -s tests`; assumptions + captain decision batch in `ASSUMPTIONS.md`.
- Public page catalog: `demo/catalog.py` collects (read-only GET + one real-browser promo-text pass) into `demo/evidence/*.json` + `demo/assets`; `demo/build.py` rebuilds `demo/` and `docs/` offline from that evidence through the engine. Never add a product, price, photo or coupon without stored evidence. Page tests drive the page script with node (`tests/test_page.py`).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
