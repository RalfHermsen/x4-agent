# Station managers: requirements and trade rules

Player-supplied game knowledge, collected 2026-08-19. This is domain knowledge
about X4, not measured project data: it has not been verified against 9.00
in-game, and menu names shift between patches. Kept here because it directly
determines which order types the agent needs in Phase 3, and which rules the
planner must know before it is allowed to advise on stations.

---

## Requirements for a station manager to function

Without these basics the manager AI stalls, regardless of its skill level.

**At least 3 stars (Management Seminars).** Buy Management Seminars from the
shops on landing platforms and hand them to the manager directly. At 3 stars the
station has a range of 3 jumps (gates), which is usually enough for a healthy
economy.

**Enough freighters and miners.** Always assign both kinds of ship to the
manager: `Subordinate -> Trade for station` and `Subordinate -> Mine for
station`. Without its own ships the manager depends entirely on passing NPC
traders.

**Enough cargo and liquid/solid storage.** The station needs both Container
Storage (for end products) and Solid/Liquid Storage (for ores and gases). If
either fills up, the manager stops directing the corresponding ships.

**An operational budget.** Always give the station at least 20 to 50 percent of
the recommended budget. Even if you produce everything yourself, the manager
needs this virtual money to open purchase orders.

## Essential trade rules

Created through `Global Orders` -> `Trade Rules`, then applied in the
`Logical Station Overview` of the factory.

### 1. Own faction first (for buy orders)

Stops the manager spending millions with NPC traders on resources (ore, silicon,
hydrogen) that your own miners can deliver for free.

- Create a trade rule "Own faction only".
- Tick `Restrict all factions`, but untick your own faction so your own ships
  are still allowed.
- Select your raw materials in the station overview and apply this rule to the
  Buy Order. The manager will then never buy from the competition.

### 2. Internal logistics (for intermediate products)

For a station producing, say, Energy Cells or Refined Metals that need to move
to another station of yours, without the AI selling them off.

- Use the same "Own faction only" rule.
- Apply it to both the Buy Order and the Sell Order of that specific
  intermediate product. Your ships then move the goods between your own
  factories for free.

### 3. Open market (for end products)

High-end products (Advanced Electronics, Hull Parts, Claytronics) should sell to
everyone for maximum profit.

- Create a rule "Open market", or use the default.
- No restrictions, anyone may buy.
- Apply to the Sell Order of your end products.

## Manual adjustments in the Logical Overview (critical when away)

The manager is poor at setting prices. Adjust this by hand for the important
products.

**Auto Pricing OFF for end products.** When storage fills up, the manager drops
the price to the minimum. Turn Automatic Pricing off and set the sell price
manually to average or slightly below (around 5 percent under average). Profit
then stays high even when you are away for hours.

**Auto Pricing to MAX for buying raw materials.** With the "own faction only"
rule, buying costs you nothing anyway because it is your own fleet. Setting the
purchase price to maximum by hand gives your own miners absolute priority to
unload there rather than somewhere else.

---

## What this means for this project

1. **Phase 3 order vocabulary.** Trade rules, price settings, budget and
   subordinate assignments are all write actions that must be possible through
   the MD bridge. This is the concrete list to tick off. All of them have
   verified script primitives; see [contracts.md](contracts.md).
2. **The sitrep does not carry these fields yet.** Manager skill, operational
   budget, storage capacity per type and the active trade rules are not in
   `save_parser.py`. Without them the planner cannot see whether the basic
   requirements are met.
3. **Guardrail material.** "Auto pricing off for end products" and "own faction
   first on raw materials" are deterministic checks, not LLM judgements. They
   belong in the Python layer as a check, not in the prompt.
4. **To be verified against 9.00** before any of it lands as a rule in
   `guidelines.md`.
