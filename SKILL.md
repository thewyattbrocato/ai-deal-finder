---
name: deal-finder
description: Find genuinely similar products across stores, the coupons each page prints, and the lowest shelf price; or make one buy, wait or verify decision. Sourced evidence only; no checkout.
---

# Deal Finder

Two modes; evidence outranks deal volume in both.

- **Similar products and their offers**: the shopper has a product (link, name or description) and wants similar ones, the offers each store prints, and the lowest price. Needs only web search and page reading. See the section below and `SIMILAR_OUTPUT.md`.
- **Purchase decision** (`## Workflow`): one defensible `buy`, `wait`, `verify` or `abstain` decision, checked by `scripts/deal-finder evaluate`.

## Hard boundaries

- Never log in, enter checkout, submit payment or personal data, mutate an account, reserve scarce inventory, negotiate, or buy anything.
- Never request a full address, credentials, payment data, government identifiers, or unrelated browsing history.
- Never claim a seller is safe or a price is guaranteed, best ever, or urgent without scope-matched evidence.
- Never count an untested coupon, delayed cash back, rebate, points, or gift card as money due today.
- V1 has no affiliate links. State that ranking is independent of commission.
- For subscriptions, financial or medical products, controlled goods, resale speculation, or negotiation, abstain without ranking.

## Similar products and their offers

One pass, at most 10 pages read in total (the same total as `DISCOVERY.md`'s caps): count each distinct link you open, blocked pages and 404s included; re-reading a page you already counted, to confirm it in a browser or raw HTML, is free. Answer in `SIMILAR_OUTPUT.md`'s template and rules. This mode reports; it gives no `buy` or `wait`.

**Reading a page.** A page reader that summarises (Claude's WebFetch) is for finding things: its prices, sizes, stock and offer words can be wrong or paraphrased. Before a price, size, stock state or offer goes in the answer, confirm it in the page's own text: a browser's text after scripts run (preferred) or raw HTML (`curl`); where they differ, the browser's visible text wins. Always confirm the price behind each lowest line. Record how each fact was read (`read`); a price or stock only a summary or a listing gave is flagged, never counted. Check that the page a browser shows is the link you opened (a shared browser can show another tab). Clicking a size or option to read its price is fine; adding to cart is not. Right after each read run `date -u +%Y-%m-%dT%H:%M:%SZ` and copy it as that page's time; never estimate a time.

**Which pages.** Take product links from search results or the store's own menu; never build or guess one. News, review and coupon sites and look-alike domains (such as `brand-shop.it.com` copies of a brand) are not stores: do not read them as one. Amazon refuses Claude's page reader (robots.txt) and Walmart answers with a "Robot or human?" page: list them under blocked with their links. Where a page is fetched from can pick its edition, currency or pickup store (a Canadian edition in CAD, a ZIP the site chose): say so, and never convert.

1. **Read the reference.** Open the product's own page and record name, brand, store, the shelf price for the size and option shown, the size, the stock and the attributes it prints. If it is out of stock or no price can be read, the answer says so first and does not count it. If the kind is sold by size and the page prints none, ask the shopper once for the size (it is on the bag or box); without an answer, go on and say so. From a description, list each attribute you assume and mark it `assumed`. Take the region and currency from the shopper or, failing that, from the reference page.
2. **Turn "this level of quality" into checkable attributes.** Pick 3 to 6 that a product page can show, each a must-have or may-vary. Coffee beans, pick from: whole bean or ground; roast level; specialty (origin and process printed) or supermarket blend; single origin or blend; organic or another certification only when printed; roast date or roasting schedule printed; bag size (may vary; compare per unit). Refills, cartridges, filters, brush heads and other parts: "fits the shopper's model" (name the model) is always a must-have. Any other kind: the attributes that change what the shopper gets and that the reference page prints (material, capacity or size, model or generation, new or refurbished, count per pack, certification), never marketing words. Ask the shopper once, and only if a missing attribute would change which products qualify; otherwise state your reading and go on.
3. **Search several stores.** Web search for the reference at other stores and for similar products (brand plus kind plus key attributes, then kind plus attributes). Never one store only. Search snippets, AI summaries and shopping or coupon sites are leads only; their prices and codes never enter the answer. When the budget is spent, stop and say so.
4. **Read each candidate's own page.** Quote the shelf price as printed for the size and option you checked; a "from" price or a range is not a shelf price (open the option, or flag it). Record the size and stock as printed (or `null`), each attribute as `same`, `differs`, `unknown` (the page does not say) or `not-read` (you did not read that part), the time from `date -u` and the link with tracking and affiliate parameters (`utm_*`, `_gsid`, `gclid`, `fbclid`, `ref`, `tag`, `aff…`) removed. A challenge page, 403, 404, empty page or a page with no price in its text goes under blocked with what happened and its link for a manual check. When a reader or raw HTML shows no price, open the page in a browser before calling it "price not readable"; never a guess. A price on a store's listing page is a lead: open the product's own page.
5. **Record the offers each page prints and shows.** Quote the store's own words for a code on the product page or a site banner (with its printed discount), a sale already in the shelf price, a subscribe or autoship price, a sign-up offer, a buy-more or case price, or a free-shipping threshold (`SIMILAR_OUTPUT.md` lists the kinds). Give each its evidence state (`retailer-stated`; `unverified` for indexed text of a page you could not read) and its gate (`none`, `email`, `sms`, `first-order`, `subscription`, `member`, `store-card`, `app`, `other`). Text hidden in the HTML but not shown on the page is not printed.
6. **Say what is and is not comparable.** For every candidate write what made it similar and what is not comparable (size, roast, certification, region or currency, new or refurbished, subscribe-only or pickup-only price, anything unknown). Out of stock in the page's text, another currency (never converted) or a must-have that differs means excluded; a must-have the page does not show, a price or stock only a summary or a listing gave, a "from" price, or a pickup price at a store the shopper did not choose means flagged. Mark the same product at another store `same_product`; it ranks first, then the most `same` attributes, excluded last. Never call two different products equivalent. If nothing similar qualified, say so first.
7. **Give the lowest price in separate lines.** *Lowest shelf price*: the lowest printed shelf price among counted items the same size as the shopper's (the reference counts); a different size competes on the per-unit line; this is the price. Less than 2% below the shopper's price is "no meaningful saving found", with both prices. If only one store's price could be counted, say so. Name each cheaper item not counted (flagged or excluded) and why. *Lowest price per unit*: the same, per unit. *If a printed code applies (not tried, may not work)*: the lowest shelf price with one ungated, store-printed code whose discount is printed in numbers; never stacked and never presented as the price; a gated code never counts; write `none` and why when nothing qualifies.
8. **Report the run.** Pages read of the budget, the searches, start and end time, how long it took and what it cost when the runtime reports it (otherwise `not reported`), each blocked page with its link, and every unknown (tax, shipping for one item, roast date, ...).

**Unit price (this mode only; the stored catalog's exact-size rule is unchanged).** One unit for the whole answer (US: per oz, fl oz or ct; metric regions: per g, ml or ct), or `none` for things sold one at a time, like shoes. Each item's unit price is its shelf price ÷ its own printed size; a case or pack counts its items ("12.5 oz (Case of 12)" is 150 oz). Never guess a size; otherwise write `not comparable: size not stated`. The arithmetic is `deal_finder/unit_price.py`'s: 2 decimals, 3 decimals when under 1.00, half up.

The shelf price is the price. A printed code seen but not tried never lowers it, and nothing is applied in a cart: no cart, login or purchase. No invented product, price, coupon, size or shipping fact; unknown stays unknown. No affiliate links or commission-influenced ranking, and no endorsement or urgency wording. With Python and the checker (this skill's folder, installed as `README.md` says), save the answer JSON beside your work (for example `deal-finder-answer.json`), run `scripts/deal-finder similar-check deal-finder-answer.json --markdown` from this skill's folder, and fix every problem it lists. Without the checker nothing checks the answer: follow `SIMILAR_OUTPUT.md` rule by rule.

## Workflow

1. Ask for the exact item or bounded need, region/currency, deadline, acceptable condition, and which attributes must stay fixed versus may vary. Ask what "local" or "similar" means rather than assuming.
2. Search at most 6 exact-item offers and 4 substitutes. Prefer fewer. A substitute qualifies only when every must-have is documented; state material differences beside savings and never imply lookalike equivalence.
3. Record each candidate's exact variant, quantity, condition, bundle, seller, fulfillment party, region, availability, source URL, absolute observation time, and evidence state.
4. Prefer merchant/manufacturer pages for current terms. Use third-party sources for discovery, history, and cross-checking. Blocked-page indexed text remains `unverified` and requires a manual check.
5. Assemble input using `README.md`'s schema and run `scripts/deal-finder evaluate <input.json>`. Without Jev, the runtime intentionally returns `verify`. With a server-side `TYPESAFE_API_KEY`, use `--live-jev`; never expose or log the key. A saved Jev response can be supplied with `--judgment`.
6. Present `buy`, `wait`, `verify`, or `abstain` exactly as defined in `DECISION_TABLE.md`. Put each caveat beside the claim it limits. In non-browsing mode, say live facts were not independently verified; one pasted offer cannot support buy or wait.

## Coupon testing

Coupon research is allowed without cart mutation. Testing in a cart is optional and requires the user's explicit yes.

1. Ask once: "May I test public coupon codes in a logged-out anonymous cart? I will stop before login or checkout, use no personal or payment data, reserve no scarce inventory, and restore an empty cart plus clean up the browser session. You can revoke this at any time."
2. Only after an actual yes, persist it with `scripts/deal-finder consent grant --file <consent.json> --session <session-id> --merchant <merchant> --attempt <attempt-id> --confirmed`. Never infer consent or add `--confirmed` without that yes. Each grant covers one merchant and one coupon attempt.
3. Before every merchant run, create a run JSON and execute `scripts/deal-finder cart-check --consent <consent.json> --run <run.json>`. Proceed only when `allowed: true`.
4. Use no more than the declared budget (maximum 3 combinations), prioritizing published terms. Stop immediately on login, checkout, personal-data, payment, account, reservation, budget, rule, or cleanup boundaries.
5. Restore a visibly empty cart, clean the browser session, and record merchant, actions, budget used/declared, stop reason, and observed cleanup. Do not claim knowledge of merchant-side identifiers.
6. Revoke immediately on request with `scripts/deal-finder consent revoke --file <consent.json>`. Any denial or uncertainty means research-only verification.

## Stale and deceptive deals

Add the optional fields below to the evidence JSON (field list in `README.md`'s schema; all are optional, and a missing field stays unknown, never guessed). Ask the shopper how fresh a price must be and set `request.freshness_window_hours`; set `request.as_of` to the current time. Each rule is run by `scripts/deal-finder evaluate`; the shopper sees one of three outcomes.

| Situation (field) | What the shopper sees |
| --- | --- |
| Price or counted coupon older than the stated window, dated in the future, or a counted coupon with no time | **Refused**: `verify`, "not trusted", with a recheck. No window stated means age is not judged. |
| Counted coupon whose conditions the page did not state (`coupon.conditions_unstated`) | **Refused** if its discount is counted; otherwise **labelled** and left out of the total. |
| Urgency or scarcity text (`urgency_signals`: countdown, "only N left", "ends tonight") | **Labelled** "not evidence of stock or a deadline" and never used to hurry the choice. **Refused** if it comes back after a reload (`repeats_on_reload`). |
| "Was" price with no dated history (`reference_price.dated_history` false) | **Labelled**; never subtracted, never shown as a saving. The saving stays unknown. |
| Seller marked unverified or with red flags (`seller_verified` false, `seller_red_flags`) | **Refused**: `verify` with a seller check. A marketplace seller nobody checked is **labelled** unknown; say nothing about its safety. |
| Affiliate-linked or sponsored offer (`affiliate_link`, `sponsored`) | A winner like this is **refused**; a losing one is **labelled**. The disclosure changes from "no affiliate links" to say so. |
| Offer for another region, or priced in another currency (`region`, `currency`) | **Left out** of the ranking and **labelled** "not comparable"; prices are never converted. No match left means `verify`. |
| Condition the shopper does not accept (`request.acceptable_conditions`, for example refurbished or open-box when only new is accepted) | **Left out** and **labelled**. With no stated conditions nothing is guessed. |
| Price that needs first-order, member or student eligibility (`eligibility_condition`, `eligibility_confirmed`) | **Refused** with one question for the shopper until they confirm; once confirmed it is **labelled** beside the price. |
| Counted code whose terms sit on a page that was not read (`coupon.terms_on_other_page`) | **Refused** if its discount is counted; otherwise **labelled** and left out of the total. |
| Email, card number, SSN-shaped text, or a login or token inside a URL anywhere in the evidence | **Rejected** before anything is sent to Jev or any other service; only the product, offer and region facts leave your context. |

Read the `labels` list in the output and put each label beside the claim it limits. A label never raises or lowers a verdict by itself; a refusal always returns `verify` with the one check that would resolve it.

## Output contract

Lead with the verdict and one next action. Show the winner and at most one decision-changing alternative. For every material claim include source, region, absolute timestamp, and one evidence state: `observed-now`, `applied-in-anonymous-cart`, `retailer-stated`, `third-party-historical`, `user-provided`, `unverified`, `rejected`, or `unknown`.

Rank known amount due today per `LANDED_COST.md`: item price minus immediate proven discount, plus shipping, mandatory fees, known tax, and required membership/bundle cost. Disclose delayed value and unproven checkout credit separately; they never enter the ranked total. Show unknowns or ranges. If ranges overlap or an unknown could flip the winner, return `verify` with exactly one check that would decide it.

For `wait`, name the history provider, item/marketplace coverage, region, and window plus an actionable recheck trigger. Never invent a future target or imply monitoring.
