"""Per-unit pricing: parsing, exact conversion, rounding, refusals, cheapest."""

import unittest
from decimal import Decimal, localcontext

from deal_finder.unit_price import (
    FACTORS, Comparison, Listing, NotComparable, Price, Size, SizeRefusal,
    cheapest, compare, parse_size, parse_size_checked, unit_price,
)

D = Decimal


def exact(expr):
    """Evaluate a Decimal expression at the module's 50-digit precision."""
    with localcontext() as ctx:
        ctx.prec = 50
        return expr()


def usd(amount):
    return Price.of(amount, "USD")


def listing(label, amount, text, currency="USD", **kw):
    return Listing(label, Price.of(amount, currency), text, source=f"https://x.test/{label}", **kw)


class ParseFormats(unittest.TestCase):
    def check(self, text, quantity, unit, count=1):
        size = parse_size(text)
        self.assertIsNotNone(size, text)
        self.assertEqual((size.quantity, size.unit, size.count), (D(quantity), unit, count), text)

    def test_oz(self): self.check("12 oz", "12", "oz")
    def test_ounce_hyphen(self): self.check("12-ounce bag", "12", "oz")
    def test_lb_decimal(self): self.check("Whole bean 2.2 lb", "2.2", "lb")
    def test_grams(self): self.check("340 g", "340", "g")
    def test_kg(self): self.check("1 kg", "1", "kg")
    def test_ml(self): self.check("250 ml", "250", "ml")
    def test_liter(self): self.check("1 L", "1", "l")
    def test_fl_oz(self): self.check("2 fl oz", "2", "fl oz")
    def test_ct(self): self.check("8 ct", "8", "ct")
    def test_pack(self): self.check("6-pack", "6", "ct")
    def test_multiplier(self): self.check("12 x 2 oz", "2", "oz", 12)
    def test_pack_of_measure(self): self.check("6 pack of 12 fl oz cans", "12", "fl oz", 6)
    def test_thousands_comma(self): self.check("1,000 g", "1000", "g")
    def test_source_text_kept(self):
        self.assertEqual(parse_size("Net wt 12 oz (340 g)").source_text, "12 oz")

    def test_no_size(self):
        for text in (None, "", "Fresh roasted coffee", "Pack-It cooler"):
            self.assertIsNone(parse_size(text), text)

    def test_same_size_two_units_is_one_size(self):
        self.assertEqual(parse_size("12 oz (340 g)").unit, "oz")

    def test_total(self):
        self.assertEqual(parse_size("12 x 2 oz").total, D(24))


class Refusals(unittest.TestCase):
    def refused(self, text, fragment):
        result = parse_size_checked(text)
        self.assertIsInstance(result, SizeRefusal, text)
        self.assertTrue(result.reason.startswith("ambiguous size: "), result.reason)
        self.assertIn(fragment, result.reason)
        self.assertIsNone(parse_size(text))

    def test_range_to(self): self.refused("8 to 12 oz", "range")
    def test_range_dash(self): self.refused("8-12 oz", "range")
    def test_range_between(self): self.refused("between 8 and 12 oz", "range")
    def test_range_repeated_unit(self): self.refused("8 oz to 12 oz", "range")
    def test_about(self): self.refused("about 12 oz", "approximate")
    def test_approx(self): self.refused("approx. 12 oz", "approximate")
    def test_tilde(self): self.refused("~12 oz", "approximate")
    def test_multi_size_no_variant(self): self.refused("Sizes: 8 oz, 12 oz, 16 oz", "no variant chosen")
    def test_bundle_mixes_sizes(self): self.refused("Bundle: 12 oz + 8 oz", "bundle mixes")
    def test_conflicting(self): self.refused("12 oz bag. Net weight 2 lb", "conflicting")
    def test_zero(self): self.refused("0 oz", "zero")
    def test_negative(self): self.refused("-5 oz", "negative")
    def test_zero_multiplier(self): self.refused("0 x 2 oz", "zero")
    def test_assorted_sizes(self): self.refused("assorted sizes", "sizes vary")
    def test_count_and_measure(self): self.refused("12 oz, 6 ct", "count and measure")

    def test_image_only(self):
        a, b = listing("a", "5", "12 oz", size_origin="image"), listing("b", "5", "12 oz")
        result = compare(a, b)
        self.assertIsInstance(result, NotComparable)
        self.assertEqual(result.reason, "ambiguous size: size appears only in an image (page A)")

    def test_chosen_variant_text_parses(self):
        self.assertEqual(parse_size("12 oz").unit, "oz")


class Conversion(unittest.TestCase):
    def test_exact_table(self):
        self.assertEqual(FACTORS["lb"], D(16) * D("28.349523125"))
        self.assertEqual(FACTORS["lb"], D("453.59237"))
        self.assertEqual(FACTORS["kg"], D(1000))
        self.assertEqual(FACTORS["l"], D(1000))
        self.assertEqual(FACTORS["fl oz"], D("29.5735295625"))

    def test_lb_to_oz_round_trip(self):
        size = parse_size("2.2 lb")
        per_oz = unit_price(usd("35.20"), size, "oz")
        per_lb = unit_price(usd("35.20"), size, "lb")
        self.assertEqual(per_oz.value, D("1"))
        self.assertEqual(per_lb.value, D("16"))
        self.assertEqual(per_lb.value / 16, per_oz.value)

    def test_kg_to_g(self):
        self.assertEqual(unit_price(usd("10"), parse_size("1 kg"), "g").value, D("0.01"))

    def test_g_to_oz_exact(self):
        value = unit_price(usd("10"), parse_size("340 g"), "oz").value
        self.assertEqual(value, exact(lambda: D("10") * D("28.349523125") / D(340)))

    def test_liter_to_ml_and_fl_oz(self):
        self.assertEqual(unit_price(usd("5"), parse_size("1 L"), "ml").value, D("0.005"))
        value = unit_price(usd("5"), parse_size("1 L"), "fl oz").value
        self.assertEqual(value, exact(lambda: D("5") * D("29.5735295625") / D(1000)))

    def test_multiplier_total(self):
        self.assertEqual(unit_price(usd("12"), parse_size("12 x 2 oz"), "oz").value, D("0.5"))

    def test_target_alias(self):
        self.assertEqual(unit_price(usd("12"), parse_size("12 oz"), "ounces").unit, "oz")

    def test_never_across_families(self):
        result = unit_price(usd("5"), parse_size("12 oz"), "ml")
        self.assertEqual(result, NotComparable("different units (mass vs volume)"))
        self.assertIsInstance(unit_price(usd("5"), parse_size("8 ct"), "oz"), NotComparable)
        self.assertIsInstance(unit_price(usd("5"), parse_size("12 oz"), "ct"), NotComparable)


class Rounding(unittest.TestCase):
    def test_three_decimals_under_one(self):
        self.assertEqual(unit_price(usd("26.99"), parse_size("2.2 lb"), "oz").display(), "0.767 USD per oz")

    def test_two_decimals_at_or_over_one(self):
        self.assertEqual(unit_price(usd("18.00"), parse_size("12 oz"), "oz").display(), "1.50 USD per oz")
        self.assertEqual(unit_price(usd("1.00"), parse_size("1 oz"), "oz").display(), "1.00 USD per oz")

    def test_half_up(self):
        self.assertEqual(unit_price(usd("0.0005"), parse_size("1 oz"), "oz").display(), "0.001 USD per oz")
        self.assertEqual(unit_price(usd("1.005"), parse_size("1 oz"), "oz").display(), "1.01 USD per oz")

    def test_value_is_stored_unrounded(self):
        value = unit_price(usd("26.99"), parse_size("2.2 lb"), "oz").value
        self.assertEqual(value, exact(lambda: D("26.99") / D("35.2")))
        self.assertGreater(len(str(value)), 20)


class CoffeeExample(unittest.TestCase):
    def test_per_oz_from_the_exact_table(self):
        a = listing("small", "18.00", "12 oz")
        b = listing("large", "26.99", "2.2 lb")
        result = compare(a, b)
        self.assertIsInstance(result, Comparison)
        self.assertEqual(result.a.value, D("1.5"))
        self.assertEqual(result.b.value, exact(lambda: D("26.99") / D("35.2")))
        self.assertEqual(result.b.display(), "0.767 USD per oz")
        self.assertEqual(result.lower_unit_price, "B")
        self.assertEqual(result.lower_shelf_price, "A")
        self.assertEqual(result.b.source_text, "2.2 lb")
        self.assertEqual(result.b.source, "https://x.test/large")


class ShelfPriceUntouched(unittest.TestCase):
    def test_unit_price_keeps_shelf_price(self):
        price = usd("26.99")
        up = unit_price(price, parse_size("2.2 lb"), "oz")
        self.assertIs(up.shelf_price, price)
        self.assertEqual(price.amount, D("26.99"))

    def test_listing_unchanged_after_compare(self):
        a, b = listing("a", "18.00", "12 oz"), listing("b", "26.99", "2.2 lb")
        compare(a, b)
        self.assertEqual((a.price.amount, b.price.amount), (D("18.00"), D("26.99")))

    def test_price_is_frozen(self):
        with self.assertRaises(Exception):
            usd("5").amount = D("1")


class PriceRules(unittest.TestCase):
    def test_float_refused(self):
        with self.assertRaises(TypeError):
            Price(5.0, "USD")
        with self.assertRaises(TypeError):
            Price.of(5.0, "USD")

    def test_currency_required_code(self):
        for bad in ("", "usd", "US", "$"):
            with self.assertRaises(ValueError):
                Price(D(1), bad)

    def test_negative_refused(self):
        with self.assertRaises(ValueError):
            usd("-1")


class CompareReasons(unittest.TestCase):
    def test_size_missing_a(self):
        self.assertEqual(compare(listing("a", "5", None), listing("b", "5", "12 oz")),
                         NotComparable("size not stated on page A"))

    def test_size_missing_b(self):
        self.assertEqual(compare(listing("a", "5", "12 oz"), listing("b", "5", "Fresh coffee")),
                         NotComparable("size not stated on page B"))

    def test_mass_vs_count(self):
        self.assertEqual(compare(listing("a", "5", "12 oz"), listing("b", "5", "8 ct")),
                         NotComparable("different units (mass vs count)"))

    def test_mass_vs_volume(self):
        self.assertEqual(compare(listing("a", "5", "12 oz"), listing("b", "5", "12 fl oz")).reason,
                         "different units (mass vs volume)")

    def test_ambiguous_names_page(self):
        result = compare(listing("a", "5", "12 oz"), listing("b", "5", "8 to 12 oz"))
        self.assertTrue(result.reason.startswith("ambiguous size: range"))
        self.assertTrue(result.reason.endswith("(page B)"))

    def test_currencies_never_mixed(self):
        result = compare(listing("a", "5", "12 oz"), listing("b", "5", "12 oz", currency="EUR"))
        self.assertIsInstance(result, NotComparable)
        self.assertIn("USD vs EUR", result.reason)

    def test_metric_default_target(self):
        result = compare(listing("a", "5", "500 g"), listing("b", "9", "1 kg"))
        self.assertEqual(result.a.unit, "g")

    def test_tie(self):
        result = compare(listing("a", "6", "12 oz"), listing("b", "12", "24 oz"))
        self.assertEqual((result.lower_unit_price, result.lower_shelf_price), ("tie", "A"))


class Cheapest(unittest.TestCase):
    def test_shelf_and_unit_differ(self):
        items = [listing("small", "18.00", "12 oz"), listing("large", "26.99", "2.2 lb")]
        result = cheapest(items)
        self.assertEqual([i.label for i in result.lowest_shelf], ["small"])
        self.assertEqual([i.label for i, _ in result.lowest_unit], ["large"])
        self.assertEqual(result.unit, "oz")
        self.assertEqual(result.note, "")
        self.assertEqual(result.lowest_unit[0][0].source, "https://x.test/large")

    def test_note_when_some_not_comparable(self):
        items = [listing("a", "18", "12 oz"), listing("b", "26.99", "2.2 lb"),
                 listing("c", "9", None), listing("d", "7", "8 ct"), listing("e", "8", "8 to 12 oz")]
        result = cheapest(items)
        self.assertEqual([i.label for i in result.lowest_shelf], ["d"])
        self.assertEqual([i.label for i, _ in result.lowest_unit], ["b"])
        self.assertEqual({i.label for i, _ in result.not_comparable}, {"c", "d", "e"})
        self.assertIn("3 of 5 items not comparable", result.note)

    def test_no_unit_ranking_with_one_sized_item(self):
        result = cheapest([listing("a", "5", "12 oz"), listing("b", "4", None)])
        self.assertEqual(result.lowest_unit, ())
        self.assertIn("no unit-price ranking", result.note)
        self.assertEqual([i.label for i in result.lowest_shelf], ["b"])

    def test_ties_kept(self):
        result = cheapest([listing("a", "6", "12 oz"), listing("b", "12", "24 oz")])
        self.assertEqual(len(result.lowest_unit), 2)

    def test_other_currency_set_aside(self):
        result = cheapest([listing("a", "5", "12 oz"), listing("b", "1", "12 oz", currency="EUR"),
                           listing("c", "4", "12 oz")])
        self.assertEqual([i.label for i in result.lowest_shelf], ["c"])
        self.assertIn("never mixed", result.note)

    def test_empty_refused(self):
        with self.assertRaises(ValueError):
            cheapest([])

    def test_wrong_family_target(self):
        with self.assertRaises(ValueError):
            cheapest([listing("a", "5", "12 oz"), listing("b", "6", "1 lb")], target_unit="ml")

    def test_shelf_prices_unchanged(self):
        items = [listing("a", "18.00", "12 oz"), listing("b", "26.99", "2.2 lb")]
        result = cheapest(items)
        self.assertEqual(result.lowest_shelf[0].price.amount, D("18.00"))
        self.assertEqual(result.lowest_unit[0][1].shelf_price.amount, D("26.99"))


if __name__ == "__main__":
    unittest.main()
