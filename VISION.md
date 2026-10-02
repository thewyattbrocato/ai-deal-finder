# Vision

AI Deal Finder exists so that ordinary AI users can make a defensible purchase decision without mistaking plausible deal claims for verified savings.
It serves a shopper who types a specific product or a kind of thing, and it turns current public evidence or safely pasted evidence into a buy, wait, or verify recommendation.
It owns exactly one thing: the purchase decision for that search, supported by direct-item deals, genuinely comparable substitute deals, and visible evidence.
A specific product gets one best place to buy.
A kind of thing may return several items that each earn buy, with the material differences stated beside each one.

## Evidence Before Confidence

Every material price, coupon, availability, seller, urgency, and history claim names its source, region, timestamp, and evidence state.
Evidence states distinguish what was observed now, retailer-stated, third-party historical, supplied by the user, unverified, rejected, or unknown.
The skill prefers first-party merchant or manufacturer evidence for current terms and uses third-party sources for discovery, history, and cross-checking.
When a primary page is blocked, that merchant stays in the result as verify with a manual-check action.
Indexed merchant text may appear only as an unverified discovery candidate.
The skill never upgrades a discovered code, search result, vendor claim, or user-provided fact into independent verification.
The skill may compare a redacted private or targeted price supplied by the shopper, but it labels that price as user-provided and never seeks access to reproduce it.
The skill never describes a seller as safe or a price as guaranteed, best ever, or urgent without scope-matched evidence.

## Two Bounded Discovery Lanes

Every search checks deals for the requested item and may check a bounded set of substitutes grounded in evidence that was actually seen.
A kind of thing shows similar items from that seen evidence without a questionnaire before the first results.
The result states which attributes differ.
When a word such as local has no evidence-backed meaning, the result states the interpretation it used.
The substitute set may grow when evaluation shows that added breadth finds materially better qualifying deals without reducing verification depth or making the answer unmanageable.
The search may stop before exhausting that bounded set when the evidence already supports a strong winner and further candidates are unlikely to change the verdict.
Every candidate is matched to its exact variant, quantity, condition, bundle, seller, fulfillment party, and region before comparison.
A substitute appears only when its material differences are stated beside its savings.
Private-label and lookalike products may be compared on documented attributes, but unknown manufacturer, durability, and performance differences stay explicit and equivalence is never implied.

## Landed Cost Over Headline Discount

The recommendation ranks known landed cost and material purchase terms rather than advertised percentage off.
Known landed cost includes item price, shipping, mandatory fees, and known tax, with every unknown component named.
A seen item price may support buy while tax, shipping, or fees are unknown, provided each unknown is named beside the price.
Quantity, size, and unit cost are normalized when they affect comparison.
Cash back, rebates, points, and gift cards remain separate conditional value and never change the ranked winner unless they reduce the amount due at checkout.
Subscription-only pricing is excluded from V1 even when the first payment is lower.
Price history names the provider, covered item or marketplace, region, and time window, and it never substitutes for current cart evidence.
Missing price history does not disqualify a current deal supported by stronger current evidence, but the skill makes no claim that the timing is historically exceptional.
Returns, warranty, delivery timing, condition, and seller signals can outweigh a nominally lower price when they change the shopper's actual decision.
Marketplace offers remain eligible when their seller, fulfillment, return, warranty, condition, and unresolved risk differences are visible beside the price.
User-stated values may outweigh the lowest landed cost only when the relevant product or seller attributes have evidence and the tradeoff is visible.
Out-of-stock offers are excluded from recommendations even when their promotional price is verified.

## Verification Stops Before Identity Or Purchase

The public page does not open a cart.
A cart test happens only in a private session, only after explicit consent, and only in a logged-out cart.
A code printed on the merchant page may be why a store is the best place to buy, and that code stays retailer-stated until a consented test or a shopper-supplied checkout result says otherwise.
Public coupon testing is optional and begins only after the user explicitly consents to that test.
The skill asks for anonymous-cart consent once, saves that decision, and continues to honor it until the user changes or revokes it.
Testing uses a logged-out anonymous cart and stops before login, checkout, payment, personal data, account mutation, or scarce-inventory reservation.
The skill treats visible empty-cart restoration plus browser-session cleanup as sufficient cleanup and does not claim knowledge of unobservable merchant-side identifiers.
Coupon stacking tests use a small declared attempt budget, prioritize combinations supported by published terms, and fall back to research-only claims when that budget or cleanup boundary would be exceeded.
When browser tools are absent, consent is absent, merchant rules prohibit testing, or a stop condition cannot be guaranteed, the skill uses research-only verification.
A code that cannot be tested remains retailer-stated or unverified unless the user safely supplies a checkout result.

## Privacy, Access, And Independence

Region, currency, deadline, acceptable condition, must-have attributes, and voluntarily disclosed eligibility are preferred over identity data.
Public member pricing may be compared as retailer-stated when the shopper volunteers matching eligibility, but it remains unverified until the shopper safely supplies a checkout result.
The skill never requests a full address, payment data, account credentials, government identifiers, or unrelated browsing history.
Browsing and non-browsing modes make different promises, and non-browsing output states plainly that live facts were not independently verified.
One pasted offer can be analyzed in non-browsing mode, but it cannot support a buy or wait verdict without comparative evidence.
The primary answer may be a visual page a person opens in a browser.
The same facts remain readable as text, and the decision does not depend on color or icons to be understood.
V1 contains no affiliate links or commission-influenced ranking, and any later monetization must keep ranking independent of commission and disclose material connections beside the recommendation.

## Scope

AI Deal Finder is not an unbounded deal feed, browser extension, continuous tracker, marketplace, seller-certification service, shopping account, rewards program, or checkout agent, and it does not promise comprehensive merchant or country coverage, guaranteed savings, or fraud prevention.
A public page may show a labeled set of already observed examples.
A query the shopper types is searched on the live web.
Those examples are not presented as that query's result unless they were observed for that query.
It does not handle subscriptions, automated purchasing, negotiation, resale speculation, financial products, medical products, controlled goods, or other high-risk categories, and it does not make legal conclusions about advertising, sellers, or regional consumer rights.
It does not name a future target price from history alone when it cannot monitor that price or ground the threshold in current actionable evidence.
The smallest deterministic engine, tests, and public page may ship before a prospective user study.
A prospective study of exact-item accuracy, substitute comparability, checkout correctness, landed-cost error, unsupported claims, and user correction burden is required before the product claims that real shoppers can trust the decision.

A change aligns when it improves an evidence-backed purchase decision, including several qualifying buys for a kind of thing, while preserving exact matching, bounded substitution, named unknowns, explicit consent, privacy, and visible uncertainty.
A change should be resisted when it increases deal volume, automation, coverage, or revenue by weakening comparability, evidence quality, ranking independence, stop conditions, or user control.
