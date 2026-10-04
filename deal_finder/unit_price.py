"""Per-unit pricing for the skill's similar-products mode (stdlib only, no network).

Pure parsing and arithmetic over text the shopper's agent already read from a
product page. A unit price exists only when the size is printed on the page;
a size is never guessed, inferred from a title's typical value, or read from
an image. The shelf price is always shown beside the unit price and is never
changed by it.

Families: mass (oz, lb, g, kg), volume (fl oz, ml, l), count (ct, pack, each).
Nothing is converted across families, and a count is never turned into mass.

Exact arithmetic: prices and sizes are Decimals. Conversion factors are the
exact table below. A unit price is computed at 50 significant digits and stored
unrounded; rounding happens only in `UnitPrice.display()`:
below 1.00 -> 3 decimals, otherwise 2 decimals, half up.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import List, Optional, Sequence, Tuple, Union

# Exact conversion table: how many base units one of each unit is.
# Mass base = gram, volume base = millilitre, count base = one item.
OZ_IN_G = Decimal("28.349523125")
FL_OZ_IN_ML = Decimal("29.5735295625")
FACTORS = {
    "g": Decimal(1),
    "kg": Decimal(1000),
    "oz": OZ_IN_G,
    "lb": 16 * OZ_IN_G,  # 1 lb = 16 oz = 453.59237 g, exactly
    "ml": Decimal(1),
    "l": Decimal(1000),
    "fl oz": FL_OZ_IN_ML,
    "ct": Decimal(1),
}
FAMILY = {
    "g": "mass", "kg": "mass", "oz": "mass", "lb": "mass",
    "ml": "volume", "l": "volume", "fl oz": "volume",
    "ct": "count",
}
METRIC = {"g", "kg", "ml", "l"}
DEFAULT_TARGET = {
    "imperial": {"mass": "oz", "volume": "fl oz", "count": "ct"},
    "metric": {"mass": "g", "volume": "ml", "count": "ct"},
}
PRECISION = 50
CONSISTENT_WITHIN = Decimal("0.01")  # '12 oz (340 g)' is one size, not two

_ALIASES = [
    ("fl oz", r"fl\.?\s*oz\.?|fluid\s+ounces?|fluid\s+oz\.?"),
    ("oz", r"oz\.?|ounces?"),
    ("lb", r"lbs?\.?|pounds?"),
    ("kg", r"kg|kilograms?|kilos?"),
    ("g", r"g|gm|grams?"),
    ("ml", r"ml|milliliters?|millilitres?"),
    ("l", r"l|liters?|litres?"),
    ("ct", r"ct\.?|counts?|packs?|pk|each|ea"),
]
_UNIT = "|".join(pattern for _, pattern in _ALIASES)
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+"
_SEP = r"\s*-?\s*"
_END = r"(?![A-Za-z])"
_START = r"(?<![\w.])"

_SIZE_RE = re.compile(
    rf"{_START}(?P<c>{_NUM})\s*[x×]\s*(?P<mn>{_NUM}){_SEP}(?P<mu>{_UNIT}){_END}"
    rf"|{_START}(?P<pc>\d+){_SEP}(?:packs?|pk|ct|count)\s+of\s+"
    rf"(?P<pn>{_NUM}){_SEP}(?P<pu>{_UNIT}){_END}"
    rf"|{_START}pack\s+of\s+(?P<k>\d+)(?![\w.])"
    rf"|{_START}(?P<neg>-?)(?P<n>{_NUM}){_SEP}(?P<u>{_UNIT}){_END}",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    rf"{_START}(?P<a>{_NUM})\s*(?P<au>{_UNIT})?\s*(?:-|–|—|to|through)\s*"
    rf"(?P<b>{_NUM})\s*(?P<bu>{_UNIT}){_END}"
    rf"|\bbetween\s+(?P<ba>{_NUM})\s*(?:{_UNIT})?\s+and\s+(?P<bb>{_NUM})\s*(?:{_UNIT}){_END}",
    re.IGNORECASE,
)
_APPROX_RE = re.compile(
    r"(?<![A-Za-z])(?:about|approx\.?|approximately|around|roughly|circa|est\.?|estimated)"
    r"\s+(?:a\s+)?[\d.]|[~≈]\s*[\d.]",
    re.IGNORECASE,
)
_VAGUE_RE = re.compile(
    r"\b(?:assorted|mixed|various|multiple|varying|different)\s+sizes\b|\bsizes\s+vary\b",
    re.IGNORECASE,
)
_BUNDLE_RE = re.compile(
    r"\b(?:bundle|assorted|variety|combo|kit|mix(?:ed)?)\b|\+|\bplus\b", re.IGNORECASE
)
_VARIANT_RE = re.compile(
    r"\b(?:sizes?|choose|select|pick|options?|variants?|available in|also in)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Price:
    """A shelf price: an exact Decimal and an explicit currency code."""

    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError("price amount must be a Decimal, never a float")
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("price amount must be a finite, non-negative Decimal")
        if not (isinstance(self.currency, str) and re.fullmatch(r"[A-Z]{3}", self.currency)):
            raise ValueError("currency must be an explicit 3-letter code such as USD")

    @classmethod
    def of(cls, amount: Union[str, int, Decimal], currency: str) -> "Price":
        if isinstance(amount, float):
            raise TypeError("price amount must be a string, int or Decimal, never a float")
        return cls(Decimal(amount), currency)

    def display(self) -> str:
        return f"{self.amount.quantize(Decimal('0.01'), ROUND_HALF_UP)} {self.currency}"


@dataclass(frozen=True)
class Size:
    """A size printed on a page. Total = quantity x count, in `unit`."""

    quantity: Decimal
    unit: str  # canonical: oz, lb, g, kg, fl oz, ml, l, ct
    count: int  # multiplier from '12 x 2 oz' or '6 pack of 12 fl oz'; else 1
    source_text: str  # the exact printed text this was read from

    @property
    def family(self) -> str:
        return FAMILY[self.unit]

    @property
    def total(self) -> Decimal:
        return self.quantity * self.count

    def base_total(self) -> Decimal:
        """Total in the family's base unit (g, ml or items)."""
        with localcontext() as ctx:
            ctx.prec = PRECISION
            return self.total * FACTORS[self.unit]


@dataclass(frozen=True)
class SizeRefusal:
    """A size was printed but must not be used. `reason` begins 'ambiguous size: '."""

    reason: str
    source_text: str


@dataclass(frozen=True)
class UnitPrice:
    value: Decimal  # exact, unrounded
    unit: str
    shelf_price: Price  # the page's price, untouched
    size: Size
    source_text: str  # the printed size text the value rests on
    source: str = ""  # the page the shelf price was read from

    def display(self) -> str:
        places = Decimal("0.001") if self.value < 1 else Decimal("0.01")
        return f"{self.value.quantize(places, ROUND_HALF_UP)} {self.shelf_price.currency} per {self.unit}"


@dataclass(frozen=True)
class NotComparable:
    reason: str


@dataclass(frozen=True)
class Listing:
    """One product page as read: its shelf price and the size text it prints."""

    label: str
    price: Price
    size_text: Optional[str]  # None = the page prints no size
    source: str = ""
    size_origin: str = "text"  # 'image' = the size is only in a picture


@dataclass(frozen=True)
class Comparison:
    a: UnitPrice
    b: UnitPrice
    lower_unit_price: str  # 'A', 'B' or 'tie'
    lower_shelf_price: str  # 'A', 'B' or 'tie'


@dataclass(frozen=True)
class Cheapest:
    lowest_shelf: Tuple[Listing, ...]
    lowest_unit: Tuple[Tuple[Listing, UnitPrice], ...]
    unit: Optional[str]
    not_comparable: Tuple[Tuple[Listing, str], ...]
    note: str


def normalize_unit(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    for canonical, pattern in _ALIASES:
        if re.fullmatch(pattern, cleaned):
            return canonical
    raise ValueError(f"unsupported unit: {text!r}")


def _num(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def _refuse(reason: str, text: str) -> SizeRefusal:
    return SizeRefusal("ambiguous size: " + reason, text)


def parse_size_checked(text: Optional[str]) -> Union[Size, SizeRefusal, None]:
    """Read the one size printed in `text`; None when no size is printed.

    Refuses (SizeRefusal) rather than guesses: ranges, 'about'/'approx',
    several different sizes (variant not chosen, mixed bundle, conflicting),
    and zero or negative quantities.
    """
    if not text or not text.strip():
        return None
    for match in _RANGE_RE.finditer(text):
        if match.group("ba") is not None:
            return _refuse(f"range ({match.group(0).strip()})", text)
        first, second = match.group("au"), match.group("bu")
        if first is None or normalize_unit(first) == normalize_unit(second):
            return _refuse(f"range ({match.group(0).strip()})", text)
    if _APPROX_RE.search(text):
        return _refuse("approximate size ('about'/'approx')", text)
    if _VAGUE_RE.search(text):
        return _refuse("sizes vary", text)

    found: List[Size] = []
    for match in _SIZE_RE.finditer(text):
        snippet = match.group(0).strip()
        if match.group("c") is not None:
            count, quantity, unit = _num(match.group("c")), _num(match.group("mn")), match.group("mu")
        elif match.group("pc") is not None:
            count, quantity, unit = Decimal(match.group("pc")), _num(match.group("pn")), match.group("pu")
        elif match.group("k") is not None:
            count, quantity, unit = Decimal(1), Decimal(match.group("k")), "ct"
        else:
            count, quantity, unit = Decimal(1), _num(match.group("n")), match.group("u")
            if match.group("neg"):
                return _refuse("negative quantity", text)
        if quantity <= 0 or count <= 0:
            return _refuse("zero or negative quantity", text)
        if count != count.to_integral_value():
            return _refuse(f"non-whole multiplier ({snippet})", text)
        found.append(Size(quantity, normalize_unit(unit), int(count), snippet))
    if not found:
        return None

    first = found[0]
    for other in found[1:]:
        if other.family != first.family:
            return _refuse(
                f"count and measure both printed ({first.source_text} / {other.source_text})", text
            )
    distinct = [first]
    for other in found[1:]:
        gap = abs(other.base_total() - first.base_total())
        if gap > first.base_total() * CONSISTENT_WITHIN:
            distinct.append(other)
    if len(distinct) > 1:
        listed = " / ".join(s.source_text for s in distinct)
        if _BUNDLE_RE.search(text):
            return _refuse(f"bundle mixes sizes ({listed})", text)
        if _VARIANT_RE.search(text):
            return _refuse(f"several sizes and no variant chosen ({listed})", text)
        return _refuse(f"conflicting sizes in one text ({listed})", text)
    return first


def parse_size(text: Optional[str]) -> Optional[Size]:
    """The printed size, or None when absent or refused (see parse_size_checked)."""
    result = parse_size_checked(text)
    return result if isinstance(result, Size) else None


def default_target(*sizes: Size) -> str:
    """Per oz / fl oz / ct unless every size is metric, then per g / ml / ct."""
    metric = all(s.unit in METRIC for s in sizes if s.family != "count")
    return DEFAULT_TARGET["metric" if metric else "imperial"][sizes[0].family]


def unit_price(
    price: Price, size: Size, target_unit: str, source: str = ""
) -> Union[UnitPrice, NotComparable]:
    """Price per `target_unit`, or NotComparable if the family differs."""
    target = normalize_unit(target_unit)
    if FAMILY[target] != size.family:
        return NotComparable(f"different units ({size.family} vs {FAMILY[target]})")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        value = price.amount * FACTORS[target] / size.base_total()
    return UnitPrice(value, target, price, size, size.source_text, source)


def _size_state(listing: Listing) -> Union[Size, str, SizeRefusal]:
    """Size, or 'missing', or a SizeRefusal."""
    if listing.size_origin == "image" and listing.size_text:
        return _refuse("size appears only in an image", listing.size_text)
    parsed = parse_size_checked(listing.size_text)
    return "missing" if parsed is None else parsed


def compare(a: Listing, b: Listing, target_unit: Optional[str] = None) -> Union[Comparison, NotComparable]:
    """Compare two pages by unit price, only when that is honest."""
    states = []
    for name, listing in (("A", a), ("B", b)):
        state = _size_state(listing)
        if state == "missing":
            return NotComparable(f"size not stated on page {name}")
        if isinstance(state, SizeRefusal):
            return NotComparable(f"{state.reason} (page {name})")
        states.append(state)
    sa, sb = states
    if sa.family != sb.family:
        return NotComparable(f"different units ({sa.family} vs {sb.family})")
    if a.price.currency != b.price.currency:
        return NotComparable(
            f"different currencies ({a.price.currency} vs {b.price.currency}); never mixed"
        )
    target = target_unit or default_target(sa, sb)
    ua = unit_price(a.price, sa, target, a.source)
    ub = unit_price(b.price, sb, target, b.source)
    if isinstance(ua, NotComparable):
        return ua
    return Comparison(ua, ub, _lower(ua.value, ub.value), _lower(a.price.amount, b.price.amount))


def _lower(x: Decimal, y: Decimal) -> str:
    return "tie" if x == y else ("A" if x < y else "B")


def cheapest(
    items: Sequence[Listing], target_unit: Optional[str] = None, currency: Optional[str] = None
) -> Cheapest:
    """Lowest shelf price, and separately the lowest unit price among items
    that are mutually comparable. Items that are not are listed with reasons.

    Ranking is in one currency (default: the first item's); other currencies
    are set aside, never converted. Unit ranking uses the family with the most
    comparable items (ties: first seen); items in another family are listed.
    """
    items = list(items)
    if not items:
        raise ValueError("cheapest needs at least one listing")
    currency = currency or items[0].price.currency
    skipped: List[Tuple[Listing, str]] = []
    priced = []
    for item in items:
        if item.price.currency == currency:
            priced.append(item)
        else:
            skipped.append((item, f"currency {item.price.currency} differs from {currency}; never mixed"))
    floor = min(i.price.amount for i in priced)
    lowest_shelf = tuple(i for i in priced if i.price.amount == floor)

    sized: List[Tuple[Listing, Size]] = []
    for item in priced:
        state = _size_state(item)
        if state == "missing":
            skipped.append((item, "size not stated on page"))
        elif isinstance(state, SizeRefusal):
            skipped.append((item, state.reason))
        else:
            sized.append((item, state))
    families: List[str] = []
    for _, size in sized:
        if size.family not in families:
            families.append(size.family)
    chosen = max(families, key=lambda f: sum(1 for _, s in sized if s.family == f)) if families else None
    group = [(i, s) for i, s in sized if s.family == chosen]
    for item, size in sized:
        if size.family != chosen:
            skipped.append((item, f"different units ({size.family} vs {chosen})"))

    lowest_unit: Tuple[Tuple[Listing, UnitPrice], ...] = ()
    unit = None
    if len(group) >= 2:
        unit = normalize_unit(target_unit) if target_unit else default_target(*[s for _, s in group])
        priced_units = [(i, unit_price(i.price, s, unit, i.source)) for i, s in group]
        if any(isinstance(u, NotComparable) for _, u in priced_units):
            raise ValueError(f"target unit {target_unit!r} is not in the {chosen} family")
        best = min(u.value for _, u in priced_units)
        lowest_unit = tuple((i, u) for i, u in priced_units if u.value == best)

    notes = []
    if skipped:
        listed = "; ".join(f"{i.label}: {why}" for i, why in skipped)
        notes.append(f"{len(skipped)} of {len(items)} items not comparable by unit price ({listed})")
    if len(group) < 2:
        notes.append("fewer than two items with a comparable printed size; no unit-price ranking")
    return Cheapest(lowest_shelf, lowest_unit, unit, tuple(skipped), "; ".join(notes))
