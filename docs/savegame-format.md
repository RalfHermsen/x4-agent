# X4 9.00 savegame format: verified structure

Everything here came out of `explore_save.py` run against a reference save from
a fresh game start on X4 9.00, build 611726. Nothing is taken from
documentation or assumed.

## Size and cost

| Measurement | Value |
|-------------|-------|
| File, gzipped | 24.2 MB |
| Elements total | 5,548,590 |
| Full streaming pass | ~10.5 s |
| Memory | flat, stays well under 1 GB |

That is a save of twenty seconds of playtime. A mature playthrough is
considerably bigger: saves from the same profile a year older run 40 to 70 MB
gzipped, so roughly two to three times as much. The streaming approach scales
linearly with that. A full etree does not.

## Top level

The root element is `savegame`, containing among others:

| Path | Meaning |
|------|---------|
| `savegame/info` | metadata: save, game, player, patches |
| `savegame/universe` | the entire game world, and the bulk of the data |
| `savegame/md` | Mission Director state, 301 `script` elements |
| `savegame/aidirector` | AI director, 22,241 `entity` elements |
| `savegame/missions` | active mission plus 24 offered missions |
| `savegame/economylog` | economy history |
| `savegame/stats` | 103 statistics as `stat id=... value=...` |
| `savegame/log`, `messages`, `tickercache` | player-facing notifications |
| `savegame/script` | script state |
| `savegame/operations` | running operations |

## The fields Phase 1 actually needs

### `savegame/info/save`

```
name = #007
date = 1787150879        (unix epoch)
```

### `savegame/info/game`

```
id = X4
version = 900            (9.00)
build = 611726
modified = 1             (mods active)
time = 19.932            (playtime in seconds)
start = x4ep1_gamestart_trade
seed = 358240979
```

`version` and `build` are exactly what you need to pin parser assumptions to a
patch, as the brief recommends.

### `savegame/info/player`

```
name = <player name>
location = {20004,190011}     (text ID pair, not a readable name)
money = 200000                (credits, whole credits here)
```

Player capital is therefore available without walking the universe tree.

**Watch the units.** This `money` is in whole credits, but trade prices
elsewhere in the same file are in hundredths of a credit, and so is
`player.money` on the Mission Director side. Three places, two scales.

`location` points into the text database (the `t/` files inside the game's cat
archives), not to a name. Readable names need a text lookup, which is what
`gamedata.py` does.

## The universe tree

Every world object hangs in a **recursive** structure:

```
savegame/universe/component
  └ connections/connection/component
      └ connections/connection/component
          └ ...
```

Each `component` carries a `class` attribute that says what it is. Classes seen
on player-owned objects: `station`, `ship_s`, `npc`, `computer`, `buildstorage`.
An object's depth says something about where it hangs (galaxy, cluster, sector,
zone, object, subobject) but is **not** constant: the same kind of object shows
up at different depths. A parser must therefore never match on depth, only on
`class` plus the ancestor chain.

Relevant attributes on a `component`:

| Attribute | Example | Note |
|-----------|---------|------|
| `class` | `ship_s`, `station` | object type |
| `macro` | `ship_tel_s_scout_01_a_macro` | exact model, links to static game data |
| `owner` | `player` | owning faction |
| `code` | `TJL-171` | in-game identifier, player visible |
| `id` | `[0xa27c2]` | internal id, hex in brackets |
| `connection` | `space`, `dock`, `parentconnection` | how it attaches to its parent |
| `knownto` | `player` | visibility |

### Filtering matters

A fresh start owns fourteen components with `owner="player"`, spread over five
different tree depths. Only a handful are interesting: one `station`, one
`ship_s`, one `ship_m`. The rest are `npc` and `computer` entries, which are
crew and ship systems. Filter on `class`, or your agent will count crew members
as fleet.

## A station's trade offers

Under a station component:

```xml
<trade><offers><production>
  <trade id="[0x4162]" buyer="[0x13519]"  ware="energycells"    price="2200"  amount="0" desired="1485"/>
  <trade id="[0x4163]" seller="[0x13519]" ware="sunriseflowers" price="11200" amount="0"/>
</production></offers></trade>
```

* `buyer` means the station **buys** that ware, `seller` that it **sells** it.
  There is no `side` attribute; you infer it from which of the two is present.
* **`price` is in hundredths of a credit.** `energycells price="1900"` is 19 Cr,
  `claytronics price="204000"` is 2,040 Cr. Verified against the known price
  ranges of several wares on a Teladi trading station. Miss this factor and you
  feed the model prices that are wrong by 100x.
* `amount` is current stock, `desired` the wanted stock when buying.

Production runs under a separate `<production><queue ware="..."/></production>`.

## Orders

Both ships and stations carry:

```xml
<orders><order id="[0x427c]" default="1" order="Wait" state="started">
  <param name="allowdocked" type="integer" value="1"/>
</order></orders>
```

The `order` attribute is the readable order name (`Wait`, and in a running game
things like `Trade`, `MiningRoutine`, `Escort`). `default="1"` means this is the
fallback order, not something the player commanded.

The order is also the best signal for what a ship *is for*. Macro names say what
a ship is; the order says what it does, and that is what a planner needs.

## Docked ships are nested inside their host

A ship with `connection="dock"` sits **inside** the subtree of the station or
ship it is docked to, not loose in the sector. In a fresh start both starting
ships hang under the player's own station. A parser that only searches at sector
level misses them entirely. The ancestor stack answers "what is this attached
to" for free.

## Visibility: what does the player know?

In a fresh start, 4 of 1,285 stations carry `knownto="player"`. In a late-game
save that number was 792. But the save contains **all** of them, including
prices and stock for stations you have never visited: 7,230 trade offers on
1,281 stations the player had not discovered.

So the omniscient view is technically available. Restricting the sitrep to
`knownto="player"` is a design decision, not a technical limit. This project
restricts it, because using the rest is simply cheating, and it makes
exploration a real strategic activity.

## Names are not readable

Sectors are called `cluster_19_sector001_macro` in the save, and objects carry
text IDs like `{20102,2102}`. The text database lives in the game's `.cat`
archives; only page 0002 sits loose in `t/`, and those are launcher strings.
Real names require a cat extraction, which is what `gamedata.py` does. Sector
and cluster names come from `libraries/mapdefaults.xml`, not from the macro
definitions in `maps/xu_ep2_universe/sectors.xml` where you would expect them.

## Consequences for `save_parser.py`

1. Stream with `iterparse`, release subtrees. No full etree.
2. Keep an explicit ancestor stack, so every object found knows which sector and
   zone it sits in.
3. Match on `class` and `owner`, never on tree depth.
4. Read `savegame/info` early and separately: that yields capital and patch
   version before the expensive universe pass begins.
5. Convert prices at the edge, once, and never mix the two scales.
