"""Every stored evidence file is either a product on the page or says why not.

Offline: reads demo/evidence/ and the built demo/index.html only. A stored
product file that is neither on the page nor carries an explicit
``excluded_reason`` (the existing exclusion mechanism in demo/catalog.py:
``extract`` honours it first) fails here, so a file cannot be dropped silently.
Evidence is never deleted: an excluded file stays stored with its reason.
"""

import copy
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import catalog  # noqa: E402

EVIDENCE = os.path.join(ROOT, "demo", "evidence")
# Folders of hand-built cards, not catalog products: each file is one card
# that build.py shows by hand (page_url on the page). Any other folder fails.
HAND_FOLDERS = {"handcards", "lavazza"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def page_entries():
    with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
        html = f.read()
    m = re.search(r'<script type="application/json" id="catalog">(.*?)</script>',
                  html, re.S)
    return json.loads(m.group(1))


PAGE = page_entries()
PAGE_URLS = [e["u"] for e in PAGE]
TOP = {fn[:-5]: load(os.path.join(EVIDENCE, fn))
       for fn in sorted(os.listdir(EVIDENCE)) if fn.endswith(".json")}


def on_page(ev):
    return ev["final_url"] in PAGE_URLS


class ExcludedEvidence(unittest.TestCase):
    def test_no_unaccounted_evidence_folder(self):
        folders = {d for d in os.listdir(EVIDENCE)
                   if os.path.isdir(os.path.join(EVIDENCE, d))}
        self.assertEqual(folders, HAND_FOLDERS)
        others = [fn for fn in os.listdir(EVIDENCE)
                  if not fn.endswith(".json") and fn not in HAND_FOLDERS]
        self.assertEqual(others, [])

    def test_each_file_is_on_the_page_or_says_why_not(self):
        silent = [i for i, ev in TOP.items()
                  if not on_page(ev) and not str(ev.get("excluded_reason") or "").strip()]
        self.assertEqual(silent, [], "stored product files neither on the page "
                         "nor carrying an excluded_reason")

    def test_a_file_on_the_page_carries_no_exclusion(self):
        both = [i for i, ev in TOP.items() if on_page(ev) and ev.get("excluded_reason")]
        self.assertEqual(both, [])

    def test_file_id_matches_its_name(self):
        for i, ev in TOP.items():
            self.assertEqual(ev["id"], i)

    def test_extractor_agrees_with_every_stored_reason(self):
        # the stored reason is what extract() returns; never a silent refusal
        for i, ev in TOP.items():
            state, val = catalog.extract(ev)
            if ev.get("excluded_reason"):
                self.assertEqual((state, val), ("excluded", ev["excluded_reason"]), i)
            else:
                self.assertEqual(state, "ok", i + " is refused by the extractor "
                                 "(%s) but stores no excluded_reason" % val)

    def test_reason_is_quoted_from_the_stored_page_data(self):
        for i, ev in TOP.items():
            if not ev.get("excluded_reason"):
                continue
            bare = copy.deepcopy(ev)
            bare.pop("excluded_reason")
            state, val = catalog.extract(bare)
            if state == "ok":
                # only a duplicate of a card that is shown may be excluded
                # although its own page reads fine
                m = re.match(r"duplicate name: the stored product name '(.+?)' is "
                             r"identical to ([a-z0-9-]+),", ev["excluded_reason"])
                self.assertTrue(m, i + " reads fine but is excluded without a "
                                "duplicate-name reason")
                kept = TOP[m.group(2)]
                self.assertTrue(on_page(kept), m.group(2) + " is not on the page")
                self.assertEqual(catalog.extract(kept)[1]["name"], m.group(1))
                self.assertEqual(catalog.extract(bare)[1]["name"], m.group(1))
            elif val == "no product data readable on the page":
                self.assertEqual(ev["json_ld"], [], i)
                self.assertIn("json_ld is empty", ev["excluded_reason"], i)
            else:
                self.assertTrue(len(ev["excluded_reason"]) > 20, i)

    def test_hand_built_cards_are_on_the_page(self):
        for folder in sorted(HAND_FOLDERS):
            for fn in sorted(os.listdir(os.path.join(EVIDENCE, folder))):
                ev = load(os.path.join(EVIDENCE, folder, fn))
                self.assertIn(ev["page_url"], PAGE_URLS, folder + "/" + fn)

    def test_counts_reconcile(self):
        hand = sum(len(os.listdir(os.path.join(EVIDENCE, d))) for d in HAND_FOLDERS)
        shown = [i for i, ev in TOP.items() if on_page(ev)]
        excluded = [i for i, ev in TOP.items() if ev.get("excluded_reason")]
        self.assertEqual(len(TOP), len(shown) + len(excluded))
        # files = products on the page + excluded; the page also shows one
        # hand-built card per file in the hand-built folders
        self.assertEqual(len(PAGE), len(shown) + hand)
        self.assertEqual(len(PAGE), len(set(PAGE_URLS)))


if __name__ == "__main__":
    unittest.main()
