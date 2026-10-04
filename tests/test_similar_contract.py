"""The similar-products output contract (SIMILAR_OUTPUT.md) is mechanically checked.

The passing fixture is the coffee answer printed in SIMILAR_OUTPUT.md itself, so
the document and the validator cannot drift apart. Each failing fixture is a
copy of it with one rule broken. The other fixtures are built from the live
acceptance runs of 2026-10-04 (Burst brush heads, Rishi tea, Open Farm's case of
12 cans, Allbirds shoes, Counter Culture's Finca El Puente): each one fails the
way that run's answer could mislead, and passes once the rule is followed.
"""

import copy
import json
import re
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from deal_finder.runtime import main
from deal_finder.similar_contract import CODE_LABEL, SIZE_NOT_STATED, render, validate

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "SIMILAR_OUTPUT.md").read_text(encoding="utf-8")
EXAMPLE = json.loads(re.search(r"```json\n(.*?)```", DOC, re.S).group(1))
TEMPLATE = re.search(r"```markdown\n(.*?)```", DOC, re.S).group(1)
LABEL = re.compile(r"^#{2,3} [^<\n]+|\*\*[A-Z][^*<]*|(?<=- )[A-Z][a-z ]+:|Stopped because:|Check it yourself:", re.M)


def example():
    return copy.deepcopy(EXAMPLE)


def candidate(answer, item_id):
    return next(c for c in answer["candidates"] if c["id"] == item_id)


def fails(answer, fragment, **kw):
    problems = validate(answer, **kw)
    return any(fragment in p for p in problems), problems


# --- fixtures from the live acceptance runs ------------------------------------------------

def item(item_id, name, store, url, at, amount, quote, size=None, unit=None, stock=("in-stock", "Add to Cart"),
         read="page-text", currency="USD", **extra):
    """One page as read: the facts the agent quoted, each read in the page's own text unless said."""
    made = {
        "id": item_id, "name": name, "store": store, "url": url, "checked_at": at,
        "shelf_price": {"amount": amount, "currency": currency, "quote": quote, "state": "observed-now", "read": read},
        "size": {"text": size[0], "quote": size[1], "read": "page-text"} if size else None,
        "availability": {"state": stock[0], "quote": stock[1], "read": "page-text"} if stock[0] != "not-stated"
        else {"state": "not-stated", "read": "page-text"},
        "offers": [],
    }
    if unit:
        made["unit_price"] = {"amount": unit[0], "currency": currency, "per": unit[1]}
    made.update(extra)
    return made


def compared(made, checks, found_via="search", status="compared", reason=None, same_product=None):
    made.update(found_via=found_via, status=status, checks=checks,
                similar_because=["read on its own page"], not_comparable=["a different listing"])
    if reason:
        made["status_reason"] = reason
    if same_product is not None:
        made["same_product"] = same_product
    return made


def answer(unit, reference, attributes, candidates, lowest, blocked, start, end, pages):
    reference["from"] = "page"
    return {
        "contract": "similar-v2",
        "request": {"said": "this is what I have; find similar ones and their coupons", "region": "US", "currency": "USD"},
        "unit": unit, "reference": reference, "attributes_used": attributes, "candidates": candidates,
        "lowest": dict({"shelf": None, "shelf_lower_not_counted": [], "unit": None, "unit_lower_not_counted": [],
                        "if_code": None, "if_code_none": "no compared page printed a code anyone can use"}, **lowest),
        "blocked": blocked,
        "run": {"searches": ["the product at other stores"], "pages_read": pages, "page_budget": 10,
                "started_at": start, "finished_at": end, "took": "not reported", "cost": "not reported",
                "stopped_because": "the useful results were read"},
        "unknowns": ["Tax: not shown on any page read."],
    }


def attribute(name, must=True):
    return {"name": name, "value": name, "must_have": must, "from": "shopper"}


def burst(amount="24.00", quote="One-time bundle $24.00", read="page-text"):
    """e1 run 1: the reader called the gated $21.00 subscribe price the 'Sale price'; the page text says $24.00."""
    reference = item("R", "Pro Brush Replacement Heads 3 Pack", "Burst Oral Care",
                     "https://burstoralcare.com/products/pro-brush-replacement-head-3-pack", "2026-10-04T20:39:57Z",
                     amount, quote, ("3 ct", "Pro Brush Replacement Heads 3 Pack"),
                     (f"{int(float(amount)) // 3}.00", "ct"), read=read)
    reference["offers"] = [{"kind": "subscribe", "quote": "Subscribe & save $21.00 Save $3.00 12 weeks",
                            "where": "product page", "state": "retailer-stated", "gate": "subscription",
                            "read": "page-text", "seen_at": "2026-10-04T20:39:57Z"}]
    quip = compared(item("C1", "Standard Soft Brush Head Refill", "quip",
                         "https://www.getquip.com/products/green-stripe-standard-soft-brush-head-refill",
                         "2026-10-04T20:39:37Z", "11.00", "One-Time Purchase $11"),
                    {"fits the Burst Pro handle": "differs", "soft bristles": "same"}, status="excluded",
                    reason="fits only quip's own handle, not the Burst Pro handle")
    walgreens = compared(item("C2", "Philips Sonicare C2 Optimal Plaque Control Replacement Brush Heads", "Walgreens",
                              "https://www.walgreens.com/q/soft+sonicare+replacement+heads", "2026-10-04T20:38:50Z",
                              "32.99", "$32.99 ($11.00 per head)", ("3 ct", "Count: 3 ea"), ("11.00", "ct"),
                              read="listing-page"),
                         {"fits the Burst Pro handle": "differs", "soft bristles": "unknown"}, status="excluded",
                         reason="fits Sonicare handles, not the Burst Pro handle; price read on a listing page")
    return answer(
        "ct", reference, [attribute("fits the Burst Pro handle"), attribute("soft bristles")], [quip, walgreens],
        {"shelf": {"id": "R", "amount": amount, "currency": "USD"},
         "shelf_lower_not_counted": [{"id": "C1", "why": "it does not fit a Burst Pro handle"}]},
        [{"store": "Walmart", "url": "https://www.walmart.com/c/kp/burst-dental", "what_happened": "a challenge page"}],
        "2026-10-04T20:38:29Z", "2026-10-04T20:40:30Z", 4,
    )


def rishi(order=("C1", "C2")):
    """e1 run 2: the identical tea at Vitacost (out of stock) and a different, flagged vanilla tea."""
    reference = item("R", "Vanilla Mint Organic Black Tea Blend Sachets", "Rishi Tea",
                     "https://www.rishi-tea.com/products/organic-vanilla-mint-black-tea-blend-teabag-sachets",
                     "2026-10-04T20:41:30Z", "10.00", "$10.00", ("10 ct", "SIZE: 10 Count"), ("1.00", "ct"))
    names = ["black tea base", "certified organic", "sachets", "vanilla and mint", "count per box"]
    vitacost = compared(item("C1", "Rishi Tea, Seasonal Edition Tea - Organic Black Tea & Botanicals Vanilla Mint",
                             "Vitacost", "https://www.vitacost.com/products/rishi-tea-seasonal-edition-tea-organic-"
                             "black-tea-botanicals-vanilla-mint-sachets-10-sachets-161006", "2026-10-04T20:42:21Z",
                             "6.20", "Regular price $10.43 Sale price $6.20", ("10 sachets", "10 Sachets"),
                             ("0.620", "ct"), stock=("out-of-stock", "Temporarily unavailable")),
                        dict.fromkeys(names, "same"), status="excluded", reason="'Temporarily unavailable'",
                        same_product=True)
    paromi = compared(item("C2", "Paromi Tea Black Tea, Bourbon Vanilla", "The Fresh Market",
                           "https://delivery.thefreshmarket.com/store/the-fresh-market/products/16909292",
                           "2026-10-04T20:43:20Z", "13.49", "Current price: $13.49", ("15 ct", "15 each"),
                           ("0.899", "ct")),
                      {"black tea base": "same", "certified organic": "same", "sachets": "same",
                       "vanilla and mint": "differs", "count per box": "differs"},
                      status="flagged", reason="priced for delivery from a store the site chose (ZIP 37211)")
    by_id = {"C1": vitacost, "C2": paromi}
    return answer(
        "ct", reference, [attribute(n, n in names[:3]) for n in names], [by_id[i] for i in order],
        {"shelf": {"id": "R", "amount": "10.00", "currency": "USD"},
         "shelf_lower_not_counted": [{"id": "C1", "why": "'Temporarily unavailable'"}],
         "unit": {"id": "R", "amount": "1.00", "per": "ct"},
         "unit_lower_not_counted": [{"id": "C1", "why": "'Temporarily unavailable'"},
                                    {"id": "C2", "why": "priced for a store the site chose; vanilla, no mint"}]},
        [{"store": "Fred Meyer", "url": "https://www.fredmeyer.com/p/paromi-organic-bourbon-vanilla-black-tea-"
          "pyramid-sachets/0089045200198", "what_happened": "the page reader timed out"}],
        "2026-10-04T20:40:39Z", "2026-10-04T20:43:35Z", 4,
    )


def open_farm(reference_unit="0.373"):
    """d1 run 1: a case of 12 cans against single cans."""
    reference = item("R", "Rustic Stew Variety Pack for Dogs", "Open Farm",
                     "https://openfarmpet.com/products/rustic-stew-variety-pack-for-dogs", "2026-10-04T20:38:40Z",
                     "55.88", "$55.88", ("12 x 12.5 oz", "12.5 oz (Case of 12)"), (reference_unit, "oz"),
                     stock=("out-of-stock", "Currently out of stock"))
    names = ["wet food", "grain-free", "container size"]
    petsmart = compared(item("C1", "Open Farm Humanely Sourced Adult Wet Dog Food - Grass-Fed Beef Stew", "PetSmart",
                             "https://www.petsmart.com/dog/food/canned-food/open-farm-adult-wet-dog-food---human-"
                             "grade-stew-125-oz-99587.html", "2026-10-04T20:39:20Z", "4.49", "Current price: $4.49",
                             ("12.5 oz", "12.5 oz"), ("0.359", "oz")),
                        dict.fromkeys(names, "same"))
    petmeds = compared(item("C2", "Open Farm Grain Free Chicken & Salmon Recipe Rustic Stew", "1-800-PetMeds",
                            "https://www.1800petmeds.com/dog/food/product/open-farm-grain-free-chicken-salmon-recipe-"
                            "rustic-stew/prod65512.html", "2026-10-04T20:38:55Z", "53.88", "$53.88",
                            ("12 x 12.5 oz", "12.5-oz, case of 12"), ("0.359", "oz"),
                            stock=("out-of-stock", "Temporarily out of stock")),
                       dict.fromkeys(names, "same"), status="excluded", reason="'Temporarily out of stock'")
    return answer(
        "oz", reference, [attribute(n, n != "container size") for n in names], [petsmart, petmeds],
        {"shelf_lower_not_counted": [{"id": "C2", "why": "'Temporarily out of stock'"}],
         "unit": {"id": "C1", "amount": "0.359", "per": "oz"}},
        [{"store": "Walmart", "url": "https://www.walmart.com/ip/seort/2969048963", "what_happened": "a challenge page"}],
        "2026-10-04T20:38:06Z", "2026-10-04T20:41:00Z", 4,
    )


def allbirds():
    """c1 run 2: shoes are sold one item at a time, so no size or unit price applies."""
    reference = item("R", "Men's Canvas Runner NZ", "Allbirds", "https://www.allbirds.com/products/mens-canvas-runner-nz",
                     "2026-10-04T20:40:55Z", "100.00", "$100", stock=("out-of-stock", "Out of stock | Notify Me"))
    names = ["men's low sneaker", "plant-fiber upper", "canvas weave"]
    veja = compared(item("C1", "CAMPO CANVAS WHITE BLACK", "VEJA official store (US)",
                         "https://www.veja-store.com/en_us/p/campo-canvas-white-black-CA0120535.html",
                         "2026-10-04T20:42:15Z", "155.00", "$155", stock=("not-stated", "")),
                    {"men's low sneaker": "unknown", "plant-fiber upper": "same", "canvas weave": "same"},
                    status="flagged", reason="it does not say it is a men's shoe")
    rackle = compared(item("C2", "Men's Alex Hemp Shoe", "Kenco Outfitters",
                           "https://kencooutfitters.com/products/rackle-mens-alex-hemp-shoe", "2026-10-04T20:42:20Z",
                           "89.99", "$89.99", stock=("not-stated", "")),
                      {"men's low sneaker": "same", "plant-fiber upper": "same", "canvas weave": "not-read"},
                      status="flagged", reason="no size option's stock could be read")
    cruiser = compared(item("C3", "Men's Canvas Cruiser", "Allbirds", "https://www.allbirds.com/products/mens-cruiser-canvas",
                            "2026-10-04T20:41:50Z", "75.00", "$75", stock=("out-of-stock", "Out of stock")),
                       dict.fromkeys(names, "same"), status="excluded", reason="'Out of stock'")
    return answer(
        "none", reference, [attribute(n, n != "canvas weave") for n in names], [veja, rackle, cruiser],
        {"shelf_lower_not_counted": [{"id": "C2", "why": "no size option's stock could be read"},
                                     {"id": "C3", "why": "'Out of stock'"}]},
        [{"store": "Cariuma", "url": "https://cariuma.com/products/oca-low-shadow-blue-canvas-sneaker-men",
          "what_happened": "'CARIUMA.com is currently closed'"}],
        "2026-10-04T20:40:50Z", "2026-10-04T20:43:00Z", 5,
    )


def finca(shopper_size=False):
    """c1 run 1: the reference page prints no bag size."""
    reference = item("R", "Finca El Puente - Honey Processed", "Counter Culture Coffee",
                     "https://counterculturecoffee.com/products/finca-el-puente-honey", "2026-10-04T20:38:10Z",
                     "25.00", "$25")
    names = ["whole bean", "honey process", "roast level", "bag size"]
    vertere = compared(item("C1", "Single Origin: Honduras Red Honey (Light Roast)", "Vertere Coffee Roasters",
                            "https://verterecoffee.com/products/single-origin-honduras-red-honey-light-roast",
                            "2026-10-04T20:39:30Z", "22.00", "$ 22.00", ("1 lb", "1 LB Bag / Whole Bean"),
                            ("1.38", "oz")),
                       {"whole bean": "same", "honey process": "same", "roast level": "same", "bag size": "unknown"})
    contrast = compared(item("C2", "Honduras - Marcala", "Contrast Coffee", "https://contrastcoffee.com/product/honduras-marcala/",
                             "2026-10-04T20:39:20Z", "21.99", "$ 21.99", ("12 oz", "Size: 12 oz. Whole Bean"),
                             ("1.83", "oz")),
                        {"whole bean": "same", "honey process": "same", "roast level": "unknown", "bag size": "unknown"},
                        status="flagged", reason="its page prints no roast level")
    made = answer(
        "oz", reference, [attribute(n, n != "bag size") for n in names], [vertere, contrast],
        {"unit": {"id": "C1", "amount": "1.38", "per": "oz"}},
        [{"store": "H-E-B", "url": "https://www.heb.com/product-detail/cafe-ol-by-h-e-b-reserve-single-origin-whole-"
          "bean-honduras-honey-coffee-12-oz/12146016", "what_happened": "an empty page"}],
        "2026-10-04T20:37:55Z", "2026-10-04T20:41:00Z", 4,
    )
    if shopper_size:
        made["reference"].update(size={"text": "12 oz", "quote": "you said: a 12 oz bag", "read": "shopper"},
                                 unit_price={"amount": "2.08", "currency": "USD", "per": "oz"})
        made["lowest"].update(shelf={"id": "R", "amount": "25.00", "currency": "USD"},
                              shelf_lower_not_counted=[{"id": "C2", "why": "its page prints no roast level"}])
    return made


class ExampleTest(unittest.TestCase):
    def test_the_coffee_answer_in_the_document_follows_the_contract(self):
        self.assertEqual(validate(example(), now=datetime.now(timezone.utc)), [])

    def test_rendered_answer_keeps_every_fixed_label_of_the_template_in_order(self):
        rendered = render(example())
        fixed = [line for line in TEMPLATE.splitlines() if not line.startswith("[")]
        labels = LABEL.findall("\n".join(fixed))
        self.assertGreaterEqual(len(labels), 14)
        position = 0
        for label in labels:
            found = rendered.find(label.strip(), position)
            self.assertGreaterEqual(found, 0, label)
            position = found + len(label.strip())
        self.assertIn("This is the price: $3.19 (11.8%) below yours at $26.99.", rendered)
        self.assertIn("This is not the price.", rendered)
        self.assertTrue(rendered.rstrip().endswith("not by commission."))

    def test_each_conditional_line_of_the_template_is_rendered_where_it_applies(self):
        conditional = LABEL.findall("\n".join(line for line in TEMPLATE.splitlines() if line.startswith("[")))
        self.assertEqual(conditional, ["**Your product:", "**Similar products:"])
        self.assertIn("**Your product:** out of stock on its page", render(open_farm()))
        self.assertIn("**Similar products:** none qualified", render(burst()))
        self.assertNotIn("**Your product:", render(example()))
        self.assertNotIn("**Similar products:", render(example()))

    def test_the_example_shows_every_contract_feature_the_brief_names(self):
        answer = example()
        self.assertEqual(answer["lowest"]["if_code"]["label"], CODE_LABEL)
        self.assertEqual(candidate(answer, "C3")["unit_price"]["amount"], "0.676")  # 3 decimals under 1.00
        self.assertEqual(answer["reference"]["offers"][0]["discount"], {"percent": "20"})
        self.assertEqual({o["kind"] for c in answer["candidates"] for o in c["offers"]} & {"autoship", "bulk"},
                         {"autoship", "bulk"})
        self.assertIn("not-read", candidate(answer, "C2")["checks"].values())
        self.assertTrue(candidate(answer, "C1")["same_product"])
        self.assertEqual(answer["lowest"]["shelf_lower_not_counted"][0]["id"], "C6")  # excluded but cheaper


class RequiredFailuresTest(unittest.TestCase):
    """The original contract rules, each still caught with its own message."""

    def assertFails(self, answer, fragment):
        found, problems = fails(answer, fragment)
        self.assertTrue(found, problems)

    def test_a_code_counted_as_a_lower_price_fails(self):
        answer = example()
        answer["lowest"]["shelf"].update(id="R", amount="21.59")
        self.assertFails(answer, "a printed code never lowers a price")

    def test_a_code_subtracted_from_a_shelf_price_fails(self):
        answer = example()
        answer["reference"]["shelf_price"]["amount"] = "21.59"
        self.assertFails(answer, "must be the price the page printed")

    def test_a_guessed_size_fails(self):
        answer = example()
        candidate(answer, "C3")["size"]["quote"] = ""
        self.assertFails(answer, "never guess a size")

    def test_a_unit_price_without_a_printed_size_fails(self):
        answer = example()
        candidate(answer, "C1")["size"] = None
        self.assertFails(answer, "needs a size printed on its page")
        candidate(answer, "C1")["unit_price"] = SIZE_NOT_STATED
        self.assertEqual(validate(answer), [])

    def test_a_size_that_is_not_the_page_size_fails(self):
        answer = example()
        candidate(answer, "C1")["size"]["text"] = "12 oz"
        self.assertFails(answer, "is not the size in the page's words")

    def test_a_unit_price_is_recomputed_with_unit_price_py(self):
        answer = example()
        candidate(answer, "C3")["unit_price"]["amount"] = "0.68"
        self.assertFails(answer, "0.676 USD per oz (2 decimals, 3 decimals under 1.00, half up")
        answer = example()
        candidate(answer, "C3")["unit_price"]["per"] = "100 g"
        self.assertFails(answer, "per must be the answer's unit 'oz'")

    def test_several_printed_sizes_with_none_chosen_fail(self):
        answer = example()
        answer["reference"]["size"]["quote"] = "SIZE 22 oz 2.2 lb 10.5 oz"
        self.assertFails(answer, "several sizes and no variant chosen")

    def test_an_unsourced_candidate_fails(self):
        for field in ("url", "checked_at", "shelf_price"):
            answer = example()
            del candidate(answer, "C3")[field]
            with self.subTest(field=field):
                self.assertFails(answer, "C3 is unsourced")

    def test_a_missing_not_comparable_reason_fails(self):
        answer = example()
        candidate(answer, "C3")["not_comparable"] = []
        self.assertFails(answer, "missing a not-comparable reason")


class ReadFromPageTextTest(unittest.TestCase):
    """Fix 1: a page reader's summary is not a quote; only the page's own text counts."""

    def test_the_burst_reader_summary_price_never_counts(self):
        wrong = burst(amount="21.00", quote="Sale price $21.00", read="reader-summary")
        found, problems = fails(wrong, "lowest.shelf must be null: no item's price could be counted")
        self.assertTrue(found, problems)
        wrong["lowest"]["shelf"] = None  # quip's $11 is still named: cheaper than your $21.00 lead
        self.assertEqual(validate(wrong), [])
        self.assertIn("**Your product:** its price comes from a page reader's summary, not confirmed in the page's "
                      "own text; it is not counted below.", render(wrong))
        self.assertEqual(validate(burst()), [])  # $24.00, confirmed in the page's text
        self.assertIn("$24.00 at Burst Oral Care", render(burst()))

    def test_a_compared_item_needs_its_price_from_the_page_text(self):
        for read in ("reader-summary", "listing-page"):
            answer = example()
            candidate(answer, "C3")["shelf_price"]["read"] = read
            with self.subTest(read=read):
                found, problems = fails(answer, "C3 is compared but its price comes from")
                self.assertTrue(found, problems)

    def test_a_summary_price_may_be_shown_as_a_flagged_lead_only(self):
        answer = example()
        carraro = candidate(answer, "C3")
        carraro["shelf_price"]["read"] = "reader-summary"
        carraro.update(status="flagged", status_reason="its price comes from a page reader's summary")
        answer["lowest"].update(shelf={"id": "R", "amount": "26.99", "currency": "USD"})
        found, problems = fails(answer, "lowest.shelf_lower_not_counted must name each cheaper item")
        self.assertTrue(found and "'C3'" in " ".join(problems), problems)

    def test_a_search_snippet_price_never_enters_the_answer(self):
        answer = example()
        candidate(answer, "C3")["shelf_price"]["read"] = "search-snippet"
        found, problems = fails(answer, "a snippet price never enters the answer")
        self.assertTrue(found, problems)

    def test_a_snippet_offer_is_unverified(self):
        answer = example()
        candidate(answer, "C1")["offers"][0]["read"] = "search-snippet"
        self.assertTrue(fails(answer, "its state is 'unverified'")[0])
        candidate(answer, "C1")["offers"][0]["state"] = "unverified"
        self.assertEqual(validate(answer), [])

    def test_stock_from_a_summary_is_confirmed_before_it_excludes(self):
        answer = rishi()
        candidate(answer, "C1")["availability"]["read"] = "reader-summary"
        found, problems = fails(answer, "C1's out-of-stock state comes from a page reader's summary")
        self.assertTrue(found, problems)
        candidate(answer, "C1")["status"] = "flagged"
        self.assertEqual(validate(answer), [])

    def test_out_of_stock_in_the_page_text_is_excluded(self):
        answer = example()
        candidate(answer, "C3")["availability"] = {"state": "out-of-stock", "quote": "Sold out", "read": "page-text"}
        self.assertTrue(fails(answer, "C3 is out of stock on its page (\"Sold out\"); exclude it")[0])

    def test_a_code_from_a_summary_never_forms_the_code_line(self):
        answer = example()
        answer["reference"]["offers"][0]["read"] = "reader-summary"
        self.assertTrue(fails(answer, "read in the page's own text")[0])

    def test_hidden_or_missing_read_fields_fail(self):
        answer = example()
        del candidate(answer, "C3")["size"]["read"]
        self.assertTrue(fails(answer, "C3.size.read must say how it was read")[0])
        answer = example()
        del candidate(answer, "C3")["availability"]
        self.assertTrue(fails(answer, "C3.availability.state must be one of")[0])


class TimesTest(unittest.TestCase):
    """Fix 2: times come from date -u; the checker holds them to the run and to its own clock."""

    def test_a_check_time_outside_the_run_fails(self):
        answer = example()
        candidate(answer, "C3")["checked_at"] = "2026-10-04T21:05:00Z"
        self.assertTrue(fails(answer, "C3.checked_at (2026-10-04T21:05:00Z) is outside the run")[0])
        answer = example()
        answer["reference"]["offers"][0]["seen_at"] = "2026-10-04T20:50:00Z"
        self.assertTrue(fails(answer, "R.offers[0].seen_at (2026-10-04T20:50:00Z) is outside the run")[0])

    def test_a_finish_time_ahead_of_the_clock_fails(self):
        now = datetime(2026, 10, 4, 21, 2, 0, tzinfo=timezone.utc)
        self.assertTrue(fails(example(), "is later than now", now=now)[0])
        self.assertEqual(validate(example(), now=datetime(2026, 10, 4, 21, 3, 40, tzinfo=timezone.utc)), [])

    def test_a_finish_before_the_start_fails(self):
        answer = example()
        answer["run"]["finished_at"] = "2026-10-04T20:00:00Z"
        self.assertTrue(fails(answer, "run.finished_at is before run.started_at")[0])


class PacksAndCountsTest(unittest.TestCase):
    """Fix 3: a case counts its cans, and the shelf line compares equal quantities only."""

    def test_the_open_farm_case_of_12_is_twelve_cans(self):
        self.assertEqual(validate(open_farm()), [])
        found, problems = fails(open_farm(reference_unit="4.470"), "0.373 USD per oz")
        self.assertTrue(found, problems)

    def test_a_single_can_is_never_the_lowest_shelf_price_against_a_case(self):
        answer = open_farm()
        answer["reference"]["availability"] = {"state": "in-stock", "quote": "Add to Cart", "read": "page-text"}
        answer["lowest"].update(shelf={"id": "C1", "amount": "4.49", "currency": "USD"}, shelf_lower_not_counted=[])
        found, problems = fails(answer, "lowest.shelf compares only items the same size as yours (12 x 12.5 oz); "
                                        "C1 is 12.5 oz: it is compared per oz on the unit line")
        self.assertTrue(found, problems)
        answer["lowest"].update(shelf={"id": "R", "amount": "55.88", "currency": "USD"},
                                shelf_lower_not_counted=[{"id": "C2", "why": "'Temporarily out of stock'"}])
        self.assertEqual(validate(answer), [])

    def test_the_render_says_nothing_counted_at_your_size_and_points_per_unit(self):
        rendered = render(open_farm())
        self.assertLess(rendered.index("**Your product:**"), rendered.index("**Lowest shelf price"))
        self.assertIn("**Lowest shelf price for 12 x 12.5 oz:** none counted at your size. Compare per oz below.",
                      rendered)
        self.assertIn("**Lowest price per oz:** $0.359 at PetSmart", rendered)

    def test_count_words_on_the_page_are_read(self):
        answer = burst()
        answer["reference"]["size"]["text"] = "3 heads"
        self.assertEqual(validate(answer), [])
        answer = rishi()
        self.assertEqual(candidate(answer, "C1")["size"]["quote"], "10 Sachets")
        self.assertEqual(validate(answer), [])

    def test_an_unknown_unit_word_names_the_accepted_ones(self):
        answer = burst()
        answer["reference"]["size"]["text"] = "3 brushes"
        found, problems = fails(answer, "R.size: '3 brushes' is not one size; write it with oz, lb, g, kg, fl oz")
        self.assertTrue(found, problems)

    def test_a_bad_reference_size_is_reported_on_the_reference_only(self):
        answer = open_farm()
        answer["reference"]["size"]["quote"] = "12.5 oz"
        problems = validate(answer)
        self.assertTrue(any(p.startswith("R.size:") for p in problems), problems)
        self.assertFalse(any(p.startswith(("C1", "C2")) for p in problems), problems)


class NoUnitTest(unittest.TestCase):
    """Fix 4: shoes have no unit; a missing reference size asks the shopper."""

    def test_shoes_take_the_no_unit_form(self):
        self.assertEqual(validate(allbirds()), [])
        answer = allbirds()
        for made in [answer["reference"]] + answer["candidates"]:
            made["unit_price"] = SIZE_NOT_STATED
        self.assertTrue(fails(answer, "unit_price must be left out when unit is 'none'")[0])

    def test_the_shoe_render_has_no_size_wording(self):
        rendered = render(allbirds())
        self.assertNotIn("size not stated", rendered)
        self.assertNotIn("not comparable", rendered)
        self.assertIn("Men's Canvas Runner NZ at Allbirds: $100.00. Out of stock (\"Out of stock | Notify Me\") on its "
                      "page.", rendered)
        self.assertIn("1. **CAMPO CANVAS WHITE BLACK** at VEJA official store (US): $155.00. Flagged:", rendered)

    def test_a_size_under_no_unit_fails(self):
        answer = allbirds()
        answer["reference"]["size"] = {"text": "2 ct", "quote": "2 pairs", "read": "page-text"}
        self.assertTrue(fails(answer, "R.size must be null when unit is 'none'")[0])

    def test_a_missing_unit_fails(self):
        answer = example()
        del answer["unit"]
        self.assertTrue(fails(answer, "unit must be one of")[0])

    def test_a_reference_with_no_size_asks_the_shopper(self):
        answer = finca()
        self.assertEqual(validate(answer), [])
        rendered = render(answer)
        self.assertIn("**Lowest shelf price:** not compared: your product's page prints no size. What size is yours?",
                      rendered)
        self.assertIn("Until then, compare per oz below.", rendered)
        self.assertIn("**Lowest price per oz:** $1.38 at Vertere Coffee Roasters", rendered)
        answer["lowest"]["shelf"] = {"id": "C1", "amount": "22.00", "currency": "USD"}
        self.assertTrue(fails(answer, "your product's size is not printed in its page's text: ask the shopper")[0])

    def test_the_size_the_shopper_gives_makes_the_comparison(self):
        answer = finca(shopper_size=True)
        self.assertEqual(validate(answer), [])
        rendered = render(answer)
        self.assertIn("**Lowest shelf price for 12 oz:** $25.00 at Counter Culture Coffee", rendered)
        self.assertIn("- Lower but not counted: Honduras - Marcala at Contrast Coffee, $21.99", rendered)
        self.assertIn("yours is $2.08 per oz", rendered)


class LowestLinesTest(unittest.TestCase):
    """Fix 5: materiality, one store, your product first, excluded cheaper items, the same product first."""

    def kimbo(self):
        answer = example()
        answer["candidates"] = [c for c in answer["candidates"] if c["id"] != "C3"]
        answer["lowest"].update(shelf={"id": "C4", "amount": "26.95", "currency": "USD"},
                                unit={"id": "C4", "amount": "0.766", "per": "oz"})
        return answer

    def test_kimbo_four_cents_lower_is_no_meaningful_saving(self):
        answer = self.kimbo()
        self.assertEqual(validate(answer), [])
        rendered = render(answer)
        self.assertIn("**Lowest shelf price for 2.2 lb:** no meaningful saving found. $26.95 at Alma Gourmet, "
                      "Kimbo - Crema Intensa Whole Bean Coffee Bag 2.2lb (1kg) (a similar product), $0.766 per oz, "
                      "read on its page at 2026-10-04T20:59:44Z, is $0.04 (0.1%) below yours at $26.99", rendered)
        self.assertNotIn("This is the price:", rendered)
        self.assertIn("**Lowest price per oz:** no meaningful saving found.", rendered)

    def test_two_percent_below_is_a_saving(self):
        answer = self.kimbo()
        for amount, unit, meaningful in (("26.45", "0.751", True), ("26.46", "0.752", False)):
            kimbo = candidate(answer, "C4")
            kimbo["shelf_price"].update(amount=amount, quote=f"${amount} 2.2lb (1kg)")
            kimbo["unit_price"]["amount"] = unit
            answer["lowest"].update(shelf={"id": "C4", "amount": amount, "currency": "USD"},
                                    unit={"id": "C4", "amount": unit, "per": "oz"})
            with self.subTest(amount=amount):
                self.assertEqual(validate(answer), [])
                self.assertEqual("no meaningful saving found" not in render(answer).split("\n\n")[2], meaningful)

    def test_only_one_store_counted_changes_the_headline(self):
        rendered = render(burst())
        self.assertIn("Only Burst Oral Care's price could be counted, so it is not shown to be lower than at other "
                      "stores.", rendered)
        self.assertNotIn("could be counted, so", render(example()))

    def test_an_excluded_cheaper_item_is_named(self):
        answer = example()
        answer["lowest"]["shelf_lower_not_counted"] = []
        found, problems = fails(answer, "lowest.shelf_lower_not_counted must name each cheaper item that is not "
                                        "counted (flagged or excluded), with why: ['C6']")
        self.assertTrue(found, problems)
        answer = example()
        answer["lowest"]["unit_lower_not_counted"] = []
        self.assertTrue(fails(answer, "lowest.unit_lower_not_counted must name each cheaper item")[0])

    def test_a_counted_item_is_not_listed_as_not_counted(self):
        answer = example()
        answer["lowest"]["shelf_lower_not_counted"].append({"id": "C4", "why": "a different brand"})
        self.assertTrue(fails(answer, "names C4, which is counted")[0])

    def test_the_identical_rishi_tea_ranks_above_a_different_tea(self):
        found, problems = fails(rishi(order=("C2", "C1")), "C1: same product, excluded, 5 same belongs before C2")
        self.assertTrue(found, problems)
        self.assertEqual(validate(rishi()), [])
        self.assertIn("1. **Rishi Tea, Seasonal Edition Tea", render(rishi()))
        self.assertIn("Same product at another store. Excluded:", render(rishi()))

    def test_the_unit_line_is_required_when_a_cheaper_unit_price_was_left_out(self):
        answer = rishi()
        answer["lowest"].update(unit=None, unit_lower_not_counted=[])
        self.assertTrue(fails(answer, "lowest.unit must be the lowest unit price")[0])

    def test_your_product_out_of_stock_is_stated_first(self):
        rendered = render(allbirds())
        self.assertTrue(rendered.split("\n\n")[2].startswith("**Your product:** out of stock on its page: "
                                                             "\"Out of stock | Notify Me\""))


class BrandLockedTest(unittest.TestCase):
    """Fix 6: when nothing similar qualifies, say so first."""

    def test_nothing_qualified_is_said_before_the_lowest_lines(self):
        rendered = render(burst())
        self.assertLess(rendered.index("**Similar products:** none qualified"), rendered.index("**Lowest shelf price"))
        self.assertIn("### Products looked at, none qualified", rendered)
        self.assertNotIn("### Similar products, most similar first", rendered)


class ContractDocumentationTest(unittest.TestCase):
    """Fix 7: every value the checker accepts is in SIMILAR_OUTPUT.md, and messages name the wrong item."""

    def test_every_offer_kind_gate_read_and_check_value_is_documented(self):
        from deal_finder import similar_contract as contract
        rules = DOC.split("## Rules each part must meet")[1].split("## JSON shape")[0]
        for value in sorted(contract.OFFER_KINDS | contract.GATES | contract.READS | contract.CHECKS
                            | contract.AVAILABILITY | contract.OFFER_WHERE | contract.UNITS):
            self.assertIn(f"`{value}`", rules, value)

    def test_new_offer_kinds_are_accepted_and_others_point_to_other(self):
        answer = example()
        candidate(answer, "C3")["offers"][0]["kind"] = "bundle"
        self.assertEqual(validate(answer), [])
        candidate(answer, "C3")["offers"][0]["kind"] = "coupon"
        self.assertTrue(fails(answer, "C3.offers[0].kind must be one of")[0])
        self.assertTrue(fails(answer, "anything else is 'other'")[0])

    def test_a_from_price_or_range_is_not_a_shelf_price(self):
        for quote in ("from $23.80", "$23.80 - $99.00"):
            answer = example()
            candidate(answer, "C3")["shelf_price"]["quote"] = quote
            with self.subTest(quote=quote):
                self.assertTrue(fails(answer, "C3 is compared but its page prints a 'from' price or a range")[0])

    def test_a_must_have_not_read_cannot_be_compared(self):
        answer = example()
        candidate(answer, "C3")["checks"]["roast level"] = "not-read"
        self.assertTrue(fails(answer, "C3 has a must-have its page does not show (or you did not read)")[0])

    def test_a_ranking_message_names_both_items(self):
        answer = example()
        answer["candidates"].reverse()
        self.assertTrue(fails(answer, "C5: similar, excluded, 3 same belongs before C6: similar, excluded, 2 same")[0])


class CodeLineTest(unittest.TestCase):
    def test_the_example_code_line_is_one_ungated_printed_code(self):
        rendered = render(example())
        self.assertIn('**If a printed code applies (not tried, may not work):** $21.59 at Lavazza USA with code AS20: '
                      '"AUTUMN SAVINGS EVENT: 20% OFF Coffee* with code AS20". This is not the price.', rendered)

    def test_the_line_needs_the_exact_label(self):
        answer = example()
        answer["lowest"]["if_code"]["label"] = "may work"
        self.assertTrue(any(CODE_LABEL in p for p in validate(answer)))

    def test_a_gated_code_never_forms_the_line(self):
        answer = example()
        answer["reference"]["offers"][0]["gate"] = "email"
        self.assertTrue(any("gated" in p for p in validate(answer)))

    def test_an_ungated_code_cannot_be_left_out(self):
        answer = example()
        answer["lowest"].update(if_code=None, if_code_none="none")
        self.assertTrue(fails(answer, "if_code is missing")[0])

    def test_the_amount_is_one_code_on_the_shelf_price(self):
        answer = example()
        answer["lowest"]["if_code"]["amount"] = "20.00"
        self.assertTrue(fails(answer, "codes never stack")[0])

    def test_a_printed_minimum_one_item_does_not_meet_rules_the_code_out(self):
        answer = example()
        answer["reference"]["offers"][0]["min_spend"] = "50.00"
        answer["lowest"].update(if_code=None, if_code_none="AS20 needs a $50 order")
        self.assertEqual(validate(answer), [])

    def test_a_code_must_appear_in_the_page_words(self):
        answer = example()
        answer["reference"]["offers"][0]["quote"] = "20% OFF Coffee"
        self.assertTrue(fails(answer, "code must appear")[0])

    def test_a_discount_must_be_numbers(self):
        answer = example()
        answer["reference"]["offers"][0]["discount"] = {"percent": "twenty"}
        self.assertTrue(fails(answer, "discount must be")[0])


class SimilarityTest(unittest.TestCase):
    def test_a_must_have_that_differs_must_be_excluded(self):
        answer = example()
        candidate(answer, "C3")["checks"]["whole bean"] = "differs"
        self.assertTrue(fails(answer, "C3 fails a must-have attribute and must be excluded")[0])

    def test_a_must_have_the_page_does_not_show_cannot_be_compared(self):
        answer = example()
        candidate(answer, "C3")["checks"]["roast level"] = "unknown"
        self.assertTrue(fails(answer, "flag it")[0])

    def test_another_currency_is_excluded_not_converted(self):
        answer = example()
        candidate(answer, "C3")["shelf_price"]["currency"] = "CAD"
        self.assertTrue(fails(answer, "never converted")[0])

    def test_a_same_product_marker_is_true_or_false(self):
        answer = example()
        candidate(answer, "C1")["same_product"] = "yes"
        self.assertTrue(fails(answer, "C1.same_product must be true or false")[0])

    def test_a_described_reference_needs_no_page(self):
        answer = example()
        reference = answer["reference"]
        for field in ("url", "checked_at", "shelf_price", "unit_price", "availability"):
            del reference[field]
        reference.update({"from": "description", "size": {"text": "2.2 lb", "quote": "you said: 2.2 lb bags",
                                                          "read": "shopper"}, "offers": []})
        answer["lowest"].update(if_code=None, if_code_none="no compared page printed a code anyone can use")
        self.assertEqual(validate(answer), [])
        rendered = render(answer)
        self.assertIn("described by you, no page", rendered)
        self.assertIn("**Your product:** described by you; no page was read; it is not counted below.", rendered)


class RunAndWordingTest(unittest.TestCase):
    def test_tracking_and_affiliate_parameters_fail(self):
        for query in ("&utm_source=shopify", "&_gsid=abc", "&tag=deals-20", "&aff_id=7"):
            answer = example()
            candidate(answer, "C3")["url"] += query
            with self.subTest(query=query):
                self.assertTrue(fails(answer, "tracking or affiliate")[0])

    def test_the_page_budget_is_at_most_ten(self):
        answer = example()
        answer["run"]["page_budget"] = 12
        self.assertTrue(fails(answer, "page_budget")[0])
        answer = example()
        answer["run"]["pages_read"] = 11
        self.assertTrue(fails(answer, "pages_read")[0])
        answer = example()
        answer["run"]["pages_read"] = 3
        self.assertTrue(fails(answer, "fewer than the distinct pages")[0])

    def test_one_store_only_fails(self):
        answer = burst()
        answer["candidates"] = []
        answer["blocked"] = []
        answer["lowest"]["shelf_lower_not_counted"] = []
        self.assertTrue(fails(answer, "never search one store only")[0])

    def test_endorsement_and_urgency_wording_fail_but_page_quotes_stay(self):
        answer = example()
        answer["unknowns"].append("This is the best deal, hurry.")
        problems = validate(answer)
        self.assertTrue(any("'best deal'" in p for p in problems))
        self.assertTrue(any("'hurry'" in p for p in problems))
        answer = example()
        candidate(answer, "C3")["offers"][0]["quote"] = "Sale price $23.80 Regular price $28.00. Hurry, best deal ever"
        self.assertEqual(validate(answer), [])

    def test_unknowns_cannot_be_empty(self):
        answer = example()
        answer["unknowns"] = []
        self.assertTrue(fails(answer, "unknowns")[0])

    def test_an_old_contract_is_refused(self):
        answer = example()
        answer["contract"] = "similar-v1"
        self.assertEqual(validate(answer), ["contract must be 'similar-v2' (SIMILAR_OUTPUT.md)"])


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
        self.assertTrue(output.startswith("## Similar products and their offers: Super Crema Whole Bean"))

    def test_a_broken_answer_lists_its_problems(self):
        answer = example()
        candidate(answer, "C3")["not_comparable"] = []
        code, output = self.run_check(answer)
        self.assertEqual(code, 1)
        self.assertIn("ok: false", output)
        self.assertIn("not-comparable reason", output)

    def test_the_command_holds_the_finish_time_to_its_clock(self):
        answer = example()
        answer["run"]["finished_at"] = "2099-01-01T00:00:00Z"
        code, output = self.run_check(answer)
        self.assertEqual(code, 1)
        self.assertIn("is later than now", output)


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

    def test_skill_has_each_section_once(self):
        for heading in ("## Similar products and their offers", "## Workflow", "## Hard boundaries"):
            self.assertEqual(len(re.findall(rf"^{re.escape(heading)}$", self.skill, re.M)), 1, heading)

    def test_skill_mode_points_at_its_contract_and_rules(self):
        section = " ".join(self.skill.split("## Similar products and their offers")[1].split("## Workflow")[0].split())
        for text in ("SIMILAR_OUTPUT.md", "deal_finder/unit_price.py", "at most 10 pages",
                     "not tried, may not work", "not comparable: size not stated", "Never one store only",
                     "confirm it in the page's own text", "date -u +%Y-%m-%dT%H:%M:%SZ", "never estimate a time",
                     "re-reading a page you already counted, to confirm it in a browser or raw HTML, is free",
                     "never build or guess one", "look-alike domains", "Walmart", "Amazon",
                     "can pick its edition, currency or pickup store", "fits the shopper's model",
                     "ask the shopper once for the size", "no meaningful saving found", "same_product",
                     "3 decimals when under 1.00", "`not-read` (you did not read that part)"):
            self.assertIn(text, section)

    def test_readme_install_section_names_real_files_and_three_prompts(self):
        section = self.readme.split("## Install and use")[1].split("## Use it as an agent skill")[0]
        self.assertIn("~/.claude/skills/deal-finder", section)
        self.assertIn("I have this coffee bag", section)
        self.assertEqual(len(re.findall(r"^\d\. \"", section, re.M)), 3)
        archived = re.search(r"HEAD \\\n\s+(.+)\n", section).group(1).split()
        raw = re.findall(r"raw\.githubusercontent\.com/thewyattbrocato/ai-deal-finder/main/([\w./-]+)", section)
        sparse = re.search(r"sparse-checkout set (.+)\n", section).group(1).split()
        self.assertIn("SIMILAR_OUTPUT.md", raw)
        for path in archived + raw + sparse:
            self.assertTrue((ROOT / path).exists(), path)

    def test_readme_says_the_two_file_install_is_unchecked_and_how_to_read_pages(self):
        section = " ".join(self.readme.split("## Install and use")[1].split("## Use it as an agent skill")[0].split())
        for text in ("**nothing checks the answer**", "--filter=blob:none --sparse", "deal-finder-answer.json",
                     "similar-check deal-finder-answer.json --markdown", "WebFetch", "`curl`", "a browser"):
            self.assertIn(text, section)


if __name__ == "__main__":
    unittest.main()
