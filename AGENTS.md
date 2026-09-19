# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- `VISION.md` is Captain-approved and frozen (verify SHA-256 `22a01c3cee76da7092e1a912c1035c6da0c05b9b97b7884a56816fe47a642cae`; never edit). Acceptance rules remain authoritative in the sibling contract files and no gate passes from implementation evidence. Run `python3 -m unittest discover -v`; keyed Jev validation remains in `KEYED_VALIDATION.md`.
- V1 build: public skill in `SKILL.md`; deterministic engine in `deal_finder/` (stdlib-only, no network/creds); tests via `python3 -m unittest discover -s tests`; assumptions + captain decision batch in `ASSUMPTIONS.md`.
- Public page catalog: `demo/catalog.py` collects (read-only GET + one real-browser promo-text pass) into `demo/evidence/*.json` + `demo/assets`; `demo/build.py` rebuilds `demo/` and `docs/` offline from that evidence through the engine. Never add a product, price, photo or coupon without stored evidence. Page tests drive the page script with node (`tests/test_page.py`).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
