"""The similar-products output contract (SIMILAR_OUTPUT.md) is mechanically checked.

The passing fixture is the coffee answer printed in SIMILAR_OUTPUT.md itself, so
the document and the validator cannot drift apart. Each failing fixture is a
copy of it with one rule broken.
"""

import copy
import json
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from deal_finder.runtime import main
from deal_finder.similar_contract import CODE_LABEL, SIZE_NOT_STATED, render, validate

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "SIMILAR_OUTPUT.md").read_text(encoding="utf-8")
EXAMPLE = json.loads(re.search(r"```json\n(.*?)```", DOC, re.S).group(1))
TEMPLATE = re.search(r"```markdown\n(.*?)```", DOC, re.S).group(1)


def example():
    return copy.deepcopy(EXAMPLE)


def candidate(answer, item_id):
    return next(c for c in answer["candidates"] if c["id"] == item_id)


def with_code(answer, gate="none"):
    """C2 (The Well, compared, $20.50) prints a 10% code on its page."""
    candidate(answer, "C2")["offers"].append({
        "kind": "code", "code": "WELL10", "quote": "Take 10% off with code WELL10",
        "where": "site banner", "state": "retailer-stated", "gate": gate,
        "discount": {"percent": "10"}, "seen_at": "2026-10-04T20:08:28Z",
    })
    return answer


class ExampleTest(unittest.TestCase):
    def test_the_coffee_answer_in_the_document_follows_the_contract(self):
        self.assertEqual(validate(example()), [])

    def test_rendered_answer_keeps_every_fixed_label_of_the_template_in_order(self):
        rendered = render(example())
        labels = re.findall(
            r"^#{2,3} [^<\n]+|\*\*[A-Z][^*<]*|(?<=- )[A-Z][a-z ]+:|Stopped because:|Check it yourself:", TEMPLATE, re.M
        )
        self.assertGreaterEqual(len(labels), 14)
        position = 0
        for label in labels:
            found = rendered.find(label.strip(), position)
            self.assertGreaterEqual(found, 0, label)
            position = found + len(label.strip())
        self.assertIn(f"**If a printed code applies ({CODE_LABEL}):** none.", rendered)
        self.assertIn("This is the price.", rendered)
        self.assertTrue(rendered.rstrip().endswith("not by commission."))

    def test_example_quotes_the_page_price_and_counts_no_code(self):
        answer = example()
        self.assertEqual(answer["lowest"]["shelf"]["amount"], answer["reference"]["shelf_price"]["amount"])
        self.assertIsNone(answer["lowest"]["if_code"])
        flagged = {c["id"] for c in answer["candidates"] if c["status"] == "flagged"}
        self.assertEqual({e["id"] for e in answer["lowest"]["shelf"]["also_lower_not_counted"]}, flagged)


class RequiredFailuresTest(unittest.TestCase):
    """The four failures the brief names, each caught with its own message."""

    def assertFails(self, answer, fragment):
        problems = validate(answer)
        self.assertTrue(any(fragment in p for p in problems), problems)

    def test_a_code_counted_as_a_lower_price_fails(self):
        answer = with_code(example())
        answer["lowest"]["shelf"].update(id="C2", amount="18.45")
        self.assertFails(answer, "a printed code never lowers a price")

    def test_a_code_subtracted_from_a_candidate_shelf_price_fails(self):
        answer = with_code(example())
        candidate(answer, "C2")["shelf_price"]["amount"] = "18.45"
        self.assertFails(answer, "must be the price the page printed")

    def test_a_guessed_size_fails(self):
        answer = example()
        candidate(answer, "C4")["size"] = {"text": "12 oz", "quote": ""}
        self.assertFails(answer, "never guess a size")

    def test_a_unit_price_without_both_printed_sizes_fails(self):
        answer = example()
        candidate(answer, "C4")["size"] = None
        self.assertFails(answer, "needs both sizes printed")
        candidate(answer, "C4")["unit_price"] = SIZE_NOT_STATED
        self.assertEqual(validate(answer), [])

    def test_a_size_that_is_not_the_page_size_fails(self):
        answer = example()
        candidate(answer, "C4")["size"]["text"] = "12 oz"
        self.assertFails(answer, "is not the size in the page's words")

    def test_a_unit_price_is_recomputed_with_unit_price_py(self):
        answer = example()
        candidate(answer, "C4")["unit_price"]["amount"] = "2.08"
        self.assertFails(answer, "3.57 per oz (deal_finder/unit_price.py)")
        answer = example()
        for item in [answer["reference"]] + answer["candidates"]:
            item["unit_price"]["per"] = "100 g"
        self.assertFails(answer, "per must be a unit deal_finder/unit_price.py uses")

    def test_several_printed_sizes_with_none_chosen_fail(self):
        answer = example()
        answer["reference"]["size"] = {"text": "12 oz", "quote": "SIZE 12 oz 24 oz 5 lb"}
        self.assertFails(answer, "several sizes and no variant chosen")

    def test_an_unsourced_candidate_fails(self):
        for field in ("url", "checked_at", "shelf_price"):
            answer = example()
            del candidate(answer, "C2")[field]
            with self.subTest(field=field):
                self.assertFails(answer, "candidates[1] is unsourced")

    def test_a_missing_not_comparable_reason_fails(self):
        answer = example()
        candidate(answer, "C2")["not_comparable"] = []
        self.assertFails(answer, "missing a not-comparable reason")


class CodeLineTest(unittest.TestCase):
    def test_an_ungated_printed_code_forms_the_labelled_line(self):
        answer = with_code(example())
        answer["lowest"]["if_code"] = {"id": "C2", "code": "WELL10", "amount": "18.45", "label": CODE_LABEL}
        self.assertEqual(validate(answer), [])
        self.assertIn("with code WELL10", render(answer))
        self.assertIn("This is not the price.", render(answer))

    def test_the_line_needs_the_exact_label(self):
        answer = with_code(example())
        answer["lowest"]["if_code"] = {"id": "C2", "code": "WELL10", "amount": "18.45", "label": "may work"}
        self.assertTrue(any(CODE_LABEL in p for p in validate(answer)))

    def test_a_gated_code_never_forms_the_line(self):
        answer = with_code(example(), gate="email")
        answer["lowest"]["if_code"] = {"id": "C2", "code": "WELL10", "amount": "18.45", "label": CODE_LABEL}
        self.assertTrue(any("gated" in p for p in validate(answer)))

    def test_an_ungated_code_cannot_be_left_out(self):
        self.assertTrue(any("if_code is missing" in p for p in validate(with_code(example()))))

    def test_the_amount_is_one_code_on_the_shelf_price(self):
        answer = with_code(example())
        answer["lowest"]["if_code"] = {"id": "C2", "code": "WELL10", "amount": "17.00", "label": CODE_LABEL}
        self.assertTrue(any("codes never stack" in p for p in validate(answer)))

    def test_a_printed_minimum_one_item_does_not_meet_rules_the_code_out(self):
        answer = with_code(example())
        candidate(answer, "C2")["offers"][-1]["min_spend"] = "50.00"
        self.assertEqual(validate(answer), [])

    def test_a_code_must_appear_in_the_page_words(self):
        answer = with_code(example())
        candidate(answer, "C2")["offers"][-1]["quote"] = "Take 10% off today"
        self.assertTrue(any("code must appear" in p for p in validate(answer)))


class SimilarityTest(unittest.TestCase):
    def test_a_must_have_that_differs_must_be_excluded(self):
        answer = example()
        candidate(answer, "C2")["checks"]["whole bean"] = "differs"
        self.assertTrue(any("must be excluded" in p for p in validate(answer)))

    def test_a_must_have_the_page_does_not_show_cannot_be_compared(self):
        answer = example()
        candidate(answer, "C3")["status"] = "compared"
        self.assertTrue(any("flag it" in p for p in validate(answer)))

    def test_candidates_are_ranked_most_similar_first(self):
        answer = example()
        answer["candidates"].reverse()
        self.assertTrue(any("most similar first" in p for p in validate(answer)))

    def test_a_cheaper_flagged_item_is_never_hidden(self):
        answer = example()
        answer["lowest"]["shelf"]["also_lower_not_counted"].pop()
        self.assertTrue(any("C3" in p for p in validate(answer)))

    def test_a_snippet_price_is_never_compared(self):
        answer = example()
        candidate(answer, "C2")["shelf_price"]["state"] = "unverified"
        self.assertTrue(any("not read on its own page" in p for p in validate(answer)))

    def test_another_currency_is_excluded_not_converted(self):
        answer = example()
        candidate(answer, "C2")["shelf_price"]["currency"] = "CAD"
        self.assertTrue(any("never converted" in p for p in validate(answer)))

    def test_a_described_reference_needs_no_page(self):
        answer = example()
        reference = answer["reference"]
        for field in ("url", "checked_at", "shelf_price", "unit_price"):
            del reference[field]
        reference.update({"from": "description", "size": {"text": "12 oz", "quote": "you said: 12 oz bags"}, "offers": []})
        answer["lowest"]["shelf"] = {"id": "C2", "amount": "20.50", "currency": "USD",
                                     "also_lower_not_counted": answer["lowest"]["shelf"]["also_lower_not_counted"]}
        answer["lowest"]["unit"] = {"id": "C2", "amount": "1.71", "per": "oz"}
        self.assertEqual(validate(answer), [])
        self.assertIn("described by you, no page", render(answer))


class RunAndWordingTest(unittest.TestCase):
    def test_tracking_and_affiliate_parameters_fail(self):
        for query in ("?utm_source=shopify", "?_gsid=abc", "?tag=deals-20", "?aff_id=7"):
            answer = example()
            candidate(answer, "C2")["url"] += query
            with self.subTest(query=query):
                self.assertTrue(any("tracking or affiliate" in p for p in validate(answer)))

    def test_the_page_budget_is_at_most_ten(self):
        answer = example()
        answer["run"]["page_budget"] = 12
        self.assertTrue(any("page_budget" in p for p in validate(answer)))
        answer = example()
        answer["run"]["pages_read"] = 11
        self.assertTrue(any("pages_read" in p for p in validate(answer)))
        answer = example()
        answer["run"]["pages_read"] = 3
        self.assertTrue(any("fewer than the distinct pages" in p for p in validate(answer)))

    def test_one_store_only_fails(self):
        answer = example()
        answer["candidates"] = [candidate(answer, "C2")]
        answer["blocked"] = []
        answer["lowest"]["shelf"]["also_lower_not_counted"] = []
        self.assertTrue(any("never search one store only" in p for p in validate(answer)))

    def test_endorsement_and_urgency_wording_fail_but_page_quotes_stay(self):
        answer = example()
        answer["unknowns"].append("This is the best deal, hurry.")
        problems = validate(answer)
        self.assertTrue(any("'best deal'" in p for p in problems))
        self.assertTrue(any("'hurry'" in p for p in problems))
        answer = example()
        candidate(answer, "C2")["offers"][0]["quote"] = "Hurry, best deal ever"
        self.assertEqual(validate(answer), [])

    def test_unknowns_cannot_be_empty(self):
        answer = example()
        answer["unknowns"] = []
        self.assertTrue(any("unknowns" in p for p in validate(answer)))


class CommandTest(unittest.TestCase):
    def run_check(self, answer, *flags):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "answer.json"
            path.write_text(json.dumps(answer), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["similar-check", str(path), *flags])
        return code, output.getvalue()

    def test_a_good_answer_passes_and_prints_its_markdown(self):
        code, output = self.run_check(example(), "--markdown")
        self.assertEqual(code, 0)
        self.assertTrue(output.startswith("## Similar products and their offers: Big Trouble"))

    def test_a_broken_answer_lists_its_problems(self):
        answer = example()
        candidate(answer, "C2")["not_comparable"] = []
        code, output = self.run_check(answer)
        self.assertEqual(code, 1)
        self.assertIn("ok: false", output)
        self.assertIn("not-comparable reason", output)


class SkillAndReadmeTest(unittest.TestCase):
    def setUp(self):
        self.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_skill_frontmatter_fits_claude_and_agent_skills_limits(self):
        front = self.skill.split("---")[1]
        name = re.search(r"^name: (.+)$", front, re.M).group(1)
        description = re.search(r"^description: (.+)$", front, re.M).group(1)
        self.assertEqual(name, "deal-finder")
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(description), 200)  # support.claude.com custom skills limit
        self.assertIn("similar products", description)

    def test_skill_mode_points_at_its_contract_and_rules(self):
        section = self.skill.split("## Similar products and their offers")[1].split("## Workflow")[0]
        for text in ("SIMILAR_OUTPUT.md", "deal_finder/unit_price.py", "at most 10 pages",
                     "not tried, may not work", "not comparable: size not stated", "Never one store only"):
            self.assertIn(text, " ".join(section.split()))

    def test_readme_install_section_names_real_files_and_three_prompts(self):
        section = self.readme.split("## Install and use")[1].split("## Use it as an agent skill")[0]
        self.assertIn("~/.claude/skills/deal-finder", section)
        self.assertIn("I have this coffee bag", section)
        self.assertEqual(len(re.findall(r"^\d\. \"", section, re.M)), 3)
        archived = re.search(r"HEAD \\\n\s+(.+)\n", section).group(1).split()
        raw = re.findall(r"raw\.githubusercontent\.com/thewyattbrocato/ai-deal-finder/main/([\w./-]+)", section)
        self.assertIn("SIMILAR_OUTPUT.md", raw)
        for path in archived + raw:
            self.assertTrue((ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main()
