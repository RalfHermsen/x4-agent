-- Lua side of the x4-agent bridge.
--
-- Why this exists at all: the Mission Director cannot manipulate strings, and
-- it has no action for setting a station's prices. Both of those are limits of
-- MD, not of X4. The game's own UI does this work through Lua, and the
-- functions it uses take ware ids as plain strings.
--
-- So MD handles what MD is good at (cues, events, creating orders) and forwards
-- anything it does not recognise here verbatim. This file parses the command,
-- finds the station itself, and calls the same functions the station
-- configuration menu calls.
--
-- Loaded through the Lua Loader API of sn_mod_support_apis; see the MD script.

local ffi = require("ffi")
local C = ffi.C

-- Declare only what we call. Wrapped per line: the game's own menus have
-- already declared some of these, and LuaJIT treats a redeclaration as an
-- error, which would take the whole file down with it.
local function declare(text)
    pcall(ffi.cdef, text)
end

declare [[ typedef uint64_t UniverseID; ]]
declare [[ uint32_t GetNumAllFactionStations(const char* factionid); ]]
declare [[ uint32_t GetAllFactionStations(UniverseID* result, uint32_t resultlen, const char* factionid); ]]
declare [[ const char* GetObjectIDCode(UniverseID objectid); ]]
declare [[ void UpdateProductionTradeOffers(UniverseID containerid); ]]
declare [[ void SetContainerWareIsBuyable(UniverseID containerid, const char* wareid, bool allowed); ]]
declare [[ void SetContainerWareIsSellable(UniverseID containerid, const char* wareid, bool allowed); ]]

-- Trade rules. A rule is a faction whitelist or blacklist, defined once at the
-- empire level and then pointed at by any number of stations and wares.
declare [[ typedef int32_t TradeRuleID; ]]
declare [[ typedef struct { uint32_t numfactions; } TradeRuleCounts; ]]
declare [[ typedef struct { uint32_t id; const char* name; uint32_t numfactions; const char** factions; bool iswhitelist; } TradeRuleInfo; ]]
declare [[ uint32_t GetNumAllTradeRules(void); ]]
declare [[ uint32_t GetAllTradeRules(TradeRuleID* result, uint32_t resultlen); ]]
declare [[ TradeRuleCounts GetTradeRuleInfoCounts(TradeRuleID id); ]]
declare [[ bool GetTradeRuleInfo(TradeRuleInfo* info, TradeRuleID id); ]]
declare [[ TradeRuleID CreateTradeRule(TradeRuleInfo info); ]]
declare [[ void SetContainerTradeRule(UniverseID containerid, TradeRuleID id, const char* ruletype, const char* wareid, bool value); ]]
declare [[ bool HasContainerOwnTradeRule(UniverseID containerid, const char* ruletype, const char* wareid); ]]

-- Blacklists. Same shape as trade rules: an empire-level object, created once
-- and then pointed at. `relation` is the whole trick: set it to "enemy" and the
-- list means "anywhere hostile" without naming a single sector, so it keeps up
-- with the diplomatic situation by itself.
declare [[ typedef uint32_t BlacklistID; ]]
declare [[ typedef struct { uint32_t id; const char* type; const char* name; bool usemacrowhitelist; uint32_t nummacros; const char** macros; bool usefactionwhitelist; uint32_t numfactions; const char** factions; const char* relation; bool hazardous; } BlacklistInfo2; ]]
declare [[ typedef struct { uint32_t nummacros; uint32_t numfactions; } BlacklistCounts; ]]
declare [[ uint32_t GetNumAllBlacklists(void); ]]
declare [[ uint32_t GetAllBlacklists(BlacklistID* result, uint32_t resultlen); ]]
declare [[ BlacklistCounts GetBlacklistInfoCounts(BlacklistID id); ]]
declare [[ bool GetBlacklistInfo2(BlacklistInfo2* info, BlacklistID id); ]]
declare [[ BlacklistID CreateBlacklist2(BlacklistInfo2 info); ]]
declare [[ void SetPlayerBlacklistDefault(BlacklistID id, const char* listtype, const char* defaultgroup, bool value); ]]
declare [[ bool IsPlayerBlacklistDefault(BlacklistID id, const char* listtype, const char* defaultgroup); ]]

-- Standing responses: what every ship of ours does when something happens to
-- it. Fleet-wide, so it covers ships bought later as well.
declare [[ typedef struct { const char* id; const char* name; const char* description; } ResponseInfo; ]]
declare [[ typedef struct { const char* id; const char* name; const char* description; uint32_t numresponses; const char* defaultresponse; bool ask; } SignalInfo; ]]
declare [[ uint32_t GetNumAllSignals(void); ]]
declare [[ uint32_t GetAllSignals(SignalInfo* result, uint32_t resultlen); ]]
declare [[ uint32_t GetNumAllResponsesToSignal(const char* signalid); ]]
declare [[ uint32_t GetAllResponsesToSignal(ResponseInfo* result, uint32_t resultlen, const char* signalid); ]]
declare [[ bool SetDefaultResponseToSignalForFaction2(const char* newresponse, bool ask, const char* signalid, const char* factionid, const char* purposeid); ]]
declare [[ const char* GetDefaultResponseToSignalForFaction2(const char* signalid, const char* factionid, const char* purposeid); ]]

-- Buying blueprints. Every signature below is copied from the game's own UI
-- Lua (menu_trader_blueprintsorlicences, menu_docked, menu_playerinfo,
-- menu_crafting), not written from memory.
declare [[ typedef struct { const char* macro; const char* ware; const char* productionmethodid; } UIBlueprint; ]]
declare [[ uint32_t GetNumBlueprints(const char* set, const char* category, const char* macroname); ]]
declare [[ uint32_t GetBlueprints(UIBlueprint* result, uint32_t resultlen, const char* set, const char* category, const char* macroname); ]]
declare [[ void LearnBlueprint(const char* wareid); ]]
declare [[ uint32_t GetNumWares(const char* tags, bool research, const char* licenceownerid, const char* exclusiontags); ]]
declare [[ uint32_t GetWares(const char** result, uint32_t resultlen, const char* tags, bool research, const char* licenceownerid, const char* exclusiontags); ]]
declare [[ uint32_t GetNumAllFactionShips(const char* factionid); ]]
declare [[ uint32_t GetAllFactionShips(UniverseID* result, uint32_t resultlen, const char* factionid); ]]
declare [[ UniverseID GetContextByClass(UniverseID componentid, const char* classname, bool includeself); ]]
declare [[ bool IsOrderSelectableFor(const char* orderdefid, UniverseID controllableid); ]]
declare [[ bool RemoveAllOrders2(UniverseID controllableid, bool onlytrade, bool onlypriority); ]]

local X4Agent = {}

-- DebugError only reaches a log file the game does not write unless it was
-- started for it, so on an ordinary run the Lua side is silent and a rejected
-- command is indistinguishable from one that worked. Raising a UI event as well
-- lets MD put the same line in the player logbook, which ends up in the
-- savegame and so in the agent's next situation report.
local function log(message)
    message = tostring(message)
    DebugError("[x4-agent lua] " .. message)
    pcall(AddUITriggeredEvent, "X4Agent", "log", message)
end

--- Every station the player owns, as {idcode = UniverseID}.
local function player_stations()
    local found = {}
    local count = C.GetNumAllFactionStations("player")
    if count == 0 then
        return found
    end
    local buffer = ffi.new("UniverseID[?]", count)
    count = C.GetAllFactionStations(buffer, count, "player")
    for i = 0, count - 1 do
        local id = buffer[i]
        local code = ffi.string(C.GetObjectIDCode(id))
        found[code] = id
    end
    return found
end

--- "price KYV-745 sunriseflowers sell 105" -> a manual price for that ware.
--
-- This is the "turn automatic pricing off" rule: left alone, a station manager
-- drops the price towards the minimum as storage fills, which is exactly what
-- happened to a warehouse full of sunriseflowers.
--
-- Two corrections, both found by sending a price and watching the savegame not
-- change. This used to also call SetContainerGlobalPriceFactor(station, -1) on
-- the belief that the menu does so alongside a per-ware price. It does not: the
-- game only ever calls that on a build storage, for build resource pricing, and
-- passing a station was an invention. And the offer itself does not refresh on
-- its own, so UpdateProductionTradeOffers has to be asked for.
local function set_price(station, args)
    local ware, side, value = args[1], args[2], tonumber(args[3])
    if not (ware and side and value) then
        log("price needs: price <IDCODE> <ware> <buy|sell> <value>")
        return false
    end
    if side ~= "buy" and side ~= "sell" then
        log("price side must be buy or sell, got " .. tostring(side))
        return false
    end

    -- buysellswitch: true is the buy side, matching the menu's own calls.
    -- Report from inside, because three attempts at this reported success and
    -- changed nothing. What is wanted is the difference between "the call never
    -- reached the engine" and "it reached it and the price is computed anyway".
    -- These are Lua wrappers, not FFI calls, and they want the UI's own id form
    -- rather than the raw UniverseID that GetAllFactionStations hands out. With
    -- the cdata they accept the call, return nil and change nothing, which is
    -- how this went unnoticed through three rounds of fixing the wrong thing.
    -- The game's own menus always wrap the container the same way.
    local id = ConvertStringTo64Bit(tostring(station))
    local buyside = (side == "buy")

    local before = GetContainerWarePrice(id, ware, buyside)
    SetContainerWarePriceOverride(id, ware, buyside, value)
    C.UpdateProductionTradeOffers(station)
    local after = GetContainerWarePrice(id, ware, buyside)

    log(string.format("price on %s: %s %s was %s, asked %d, now %s",
                      args.code, ware, side, tostring(before), value, tostring(after)))
    return true
end

--- "tradeware KYV-745 energycells buy off" -> stop buying or selling a ware.
local function set_tradeware(station, args)
    local ware, side, state = args[1], args[2], args[3]
    if not (ware and side and state) then
        log("tradeware needs: tradeware <IDCODE> <ware> <buy|sell> <on|off>")
        return false
    end
    local allowed = (state == "on")
    if side == "buy" then
        C.SetContainerWareIsBuyable(station, ware, allowed)
    elseif side == "sell" then
        C.SetContainerWareIsSellable(station, ware, allowed)
    else
        log("tradeware side must be buy or sell, got " .. tostring(side))
        return false
    end
    log(string.format("%s %s %s is now %s", args.code, side, ware, state))
    return true
end

-- The rule the agent applies when it wants "our own ships only". Created once,
-- on first use, and found again by this exact name afterwards. Rules the player
-- made by hand are never touched.
local OWN_FACTION_RULE = "x4-agent: own faction only"

--- A C string that stays alive as long as `keep` does.
--
-- Assigning a Lua string straight into a `const char*` field looks like it
-- works and then hands the engine a pointer to memory LuaJIT is free to
-- reclaim. The game's own menus solve this with Helper.ffiNewString; this is
-- the same idea without the dependency.
local function cstring(text, keep)
    local buffer = ffi.new("char[?]", #text + 1)
    ffi.copy(buffer, text)
    keep[#keep + 1] = buffer
    return buffer
end

--- The id of the empire trade rule with this name, or nil.
local function find_trade_rule(name)
    local count = C.GetNumAllTradeRules()
    if count == 0 then
        return nil
    end
    local ids = ffi.new("TradeRuleID[?]", count)
    count = C.GetAllTradeRules(ids, count)
    for i = 0, count - 1 do
        local info = ffi.new("TradeRuleInfo")
        -- GetTradeRuleInfo fills a faction array the caller allocates, so its
        -- size has to be asked for first. Zero factions still needs somewhere
        -- to point.
        local numfactions = C.GetTradeRuleInfoCounts(ids[i]).numfactions
        local factions = ffi.new("const char*[?]", math.max(numfactions, 1))
        info.numfactions = numfactions
        info.factions = factions
        if C.GetTradeRuleInfo(info, ids[i]) and ffi.string(info.name) == name then
            return ids[i]
        end
    end
    return nil
end

--- Create the "own faction only" rule: a whitelist containing just us.
local function create_own_faction_rule()
    local keep = {}
    local factions = ffi.new("const char*[1]")
    factions[0] = cstring("player", keep)

    local info = ffi.new("TradeRuleInfo")
    info.name = cstring(OWN_FACTION_RULE, keep)
    info.iswhitelist = true
    info.numfactions = 1
    info.factions = factions

    local id = C.CreateTradeRule(info)
    if id == 0 then
        log("could not create the trade rule " .. OWN_FACTION_RULE)
        return nil
    end
    log("created trade rule " .. OWN_FACTION_RULE .. " (id " .. tonumber(id) .. ")")
    return id
end

local RULE_TYPES = { buy = true, sell = true, supply = true, build = true }
local ALL_WARES = { ["-"] = true, all = true, any = true, ["*"] = true }

--- "traderule KYV-745 ore buy own" -> only buy ore from our own ships.
--
-- This is the one rule that reliably saves money on an unattended empire: a
-- station manager with credits will happily pay an NPC trader for ore that our
-- own miners are already bringing in for nothing.
--
-- `default` is the reverse, and it is deliberately not called "anyone": it
-- clears this station's own rule so it follows the empire default again, which
-- is what the station configuration menu's override checkbox does.
local function set_trade_rule(station, args)
    local ware, side, mode = args[1], args[2], args[3]
    if not (ware and side and mode) then
        log("traderule needs: traderule <IDCODE> <ware|-> <buy|sell|both> <own|default>")
        return false
    end
    if not (RULE_TYPES[side] or side == "both") then
        log("traderule side must be buy, sell, both, supply or build, got " .. tostring(side))
        return false
    end

    -- An empty ware id is how the game addresses the container as a whole.
    ware = ALL_WARES[ware] and "" or ware
    local sides = (side == "both") and { "buy", "sell" } or { side }

    local id, value
    if mode == "own" then
        id = find_trade_rule(OWN_FACTION_RULE) or create_own_faction_rule()
        if not id then
            return false
        end
        value = true
    elseif mode == "default" then
        id, value = -1, false
    else
        log("traderule mode must be own or default, got " .. tostring(mode))
        return false
    end

    for _, ruletype in ipairs(sides) do
        C.SetContainerTradeRule(station, id, ruletype, ware, value)
    end

    -- Report what the game says afterwards, not what we asked for. Trade rules
    -- are not written to the savegame, so this logbook line is the only
    -- evidence that the call landed.
    local confirmed = C.HasContainerOwnTradeRule(station, sides[1], ware)
    log(string.format("%s: %s %s is now %s (own rule: %s)", args.code, side,
                      (ware == "") and "everything" or ware, mode,
                      tostring(confirmed)))
    return true
end

-- The blacklist the agent applies when asked to keep ships out of hostile
-- space. Named so it can be found again, and never confused with one the
-- player made by hand.
local AVOID_HOSTILE = "x4-agent: avoid hostile space"
local BLACKLIST_GROUPS = { "civilian", "military" }

--- The id of the blacklist with this name, or nil.
local function find_blacklist(name)
    local count = C.GetNumAllBlacklists()
    if count == 0 then
        return nil
    end
    local ids = ffi.new("BlacklistID[?]", count)
    count = C.GetAllBlacklists(ids, count)
    for i = 0, count - 1 do
        local counts = C.GetBlacklistInfoCounts(ids[i])
        local info = ffi.new("BlacklistInfo2")
        local macros = ffi.new("const char*[?]", math.max(counts.nummacros, 1))
        local factions = ffi.new("const char*[?]", math.max(counts.numfactions, 1))
        info.nummacros, info.macros = counts.nummacros, macros
        info.numfactions, info.factions = counts.numfactions, factions
        if C.GetBlacklistInfo2(info, ids[i]) and ffi.string(info.name) == name then
            return ids[i]
        end
    end
    return nil
end

--- Create the "anywhere hostile" travel blacklist.
--
-- No sectors and no factions are listed. `relation = "enemy"` does the work,
-- and it keeps working as relations change: a faction that turns on us is
-- covered the moment it does, without anyone editing a list.
local function create_avoid_hostile()
    local keep = {}
    local info = ffi.new("BlacklistInfo2")
    info.type = cstring("sectortravel", keep)
    info.name = cstring(AVOID_HOSTILE, keep)
    info.relation = cstring("enemy", keep)
    info.hazardous = false
    info.usemacrowhitelist = false
    info.nummacros = 0
    info.macros = ffi.new("const char*[1]")
    info.usefactionwhitelist = false
    info.numfactions = 0
    info.factions = ffi.new("const char*[1]")

    local id = C.CreateBlacklist2(info)
    if id == 0 then
        log("could not create the blacklist " .. AVOID_HOSTILE)
        return nil
    end
    log("created blacklist " .. AVOID_HOSTILE .. " (id " .. tonumber(id) .. ")")
    return id
end

--- "avoid hostile on" -> no ship of ours travels through hostile sectors.
--
-- Set as the player default rather than ship by ship, so it covers ships bought
-- later as well. That is the difference between a rule and a chore.
local function set_avoid_hostile(args)
    local state = args[1]
    if state ~= "on" and state ~= "off" then
        log("avoid needs: avoid hostile <on|off>")
        return false
    end
    local wanted = (state == "on")

    local id = find_blacklist(AVOID_HOSTILE)
    if not id then
        if not wanted then
            log("avoid hostile off: no such blacklist, nothing to undo")
            return true
        end
        id = create_avoid_hostile()
        if not id then
            return false
        end
    end

    local applied = {}
    for _, group in ipairs(BLACKLIST_GROUPS) do
        C.SetPlayerBlacklistDefault(id, "sectortravel", group, wanted)
        applied[#applied + 1] = string.format("%s=%s", group,
            tostring(C.IsPlayerBlacklistDefault(id, "sectortravel", group)))
    end
    log("avoid hostile " .. state .. " -> " .. table.concat(applied, " "))
    return true
end

--- "list signals" -> write every signal and its responses to the logbook.
--
-- The ids are not in any file this project can read; the engine holds them.
-- Rather than guess at "attacked" and "flee" and then wonder why nothing
-- changed, ask the game what it accepts and read the answer back.
local function list_signals()
    local count = C.GetNumAllSignals()
    if count == 0 then
        log("the game reports no signals at all")
        return false
    end
    local buf = ffi.new("SignalInfo[?]", count)
    count = C.GetAllSignals(buf, count)
    for i = 0, count - 1 do
        local id = ffi.string(buf[i].id)
        local options = {}
        local n = C.GetNumAllResponsesToSignal(id)
        if n > 0 then
            local rbuf = ffi.new("ResponseInfo[?]", n)
            n = C.GetAllResponsesToSignal(rbuf, n, id)
            for j = 0, n - 1 do
                options[#options + 1] = ffi.string(rbuf[j].id)
            end
        end
        log(string.format("signal %s -> now %s, options: %s", id,
                          ffi.string(buf[i].defaultresponse),
                          table.concat(options, " ")))
    end
    return true
end

--- "respond <signal> <response>" -> set it for the whole fleet.
--
-- purposeid "" means every purpose: traders, miners, scouts and fighters alike.
-- ask=false so nothing stops to put a question on screen while the agent runs
-- unattended.
local function set_response(args)
    local signal, response = args[1], args[2]
    if not (signal and response) then
        log("respond needs: respond <signalid> <responseid>")
        return false
    end
    C.SetDefaultResponseToSignalForFaction2(response, false, signal, "player", "")
    local now = C.GetDefaultResponseToSignalForFaction2(signal, "player", "")
    log(string.format("respond %s: asked for %s, game now says %s",
                      signal, response, now ~= nil and ffi.string(now) or "nil"))
    return true
end

-- The one save slot the agent may write. The bridge's 'save' is an autosave,
-- and autosaves rotate over the player's newest saves (tasks/lessons.md L6e).
-- The slot is fixed here and never taken from the command, so nothing that
-- arrives over the pipe, model or outbox, can write any other slot. The owner
-- gave this one up for the agent on 2026-10-18. SaveGame is the global the
-- game's own save menu calls (gameoptions.lua).
local AGENT_SLOT = "save_008"

-- Which loaded copy of this file handled a command. Two different values in
-- the logbook for one command means the file was loaded and registered twice;
-- the same value twice means MD raised the event twice.
local CHUNK = string.sub(tostring({}), -6)

local function save_agent_slot(args)
    SaveGame(AGENT_SLOT, "x4-agent")
    log("savegame requested into " .. AGENT_SLOT .. " (chunk " .. CHUNK .. ")")
    return true
end

--- Every ship the player owns, as {idcode = UniverseID}.
local function player_ships()
    local found = {}
    local count = C.GetNumAllFactionShips("player")
    if count == 0 then
        return found
    end
    local buffer = ffi.new("UniverseID[?]", count)
    count = C.GetAllFactionShips(buffer, count, "player")
    for i = 0, count - 1 do
        found[ffi.string(C.GetObjectIDCode(buffer[i]))] = buffer[i]
    end
    return found
end

local function owned_blueprints()
    local owned = {}
    local count = C.GetNumBlueprints("", "", "")
    if count == 0 then
        return owned
    end
    local buffer = ffi.new("UIBlueprint[?]", count)
    count = C.GetBlueprints(buffer, count, "", "", "")
    for i = 0, count - 1 do
        owned[ffi.string(buffer[i].ware)] = true
    end
    return owned
end

local function faction_sells_module(faction, ware)
    -- What the faction representative would list: the same tag, faction and
    -- exclusions the blueprint menu asks for.
    local count = C.GetNumWares("module", false, faction, "noplayerblueprint missiononly")
    if count == 0 then
        return false
    end
    local buffer = ffi.new("const char*[?]", count)
    count = C.GetWares(buffer, count, "module", false, faction, "noplayerblueprint missiononly")
    for i = 0, count - 1 do
        if ffi.string(buffer[i]) == ware then
            return true
        end
    end
    return false
end

--- "blueprint module_gen_prod_water_01 TJL-171" -> buy a module blueprint, paid.
--
-- Bought from the faction whose station TJL-171 is docked at: the agent may buy
-- remotely, but only where one of its ships actually is (owner's rule,
-- 2026-10-18). The order of checks and the payment follow the game's own
-- blueprint menu. LearnBlueprint does not take money, and neither does MD's
-- add_blueprints; the menu pays with a separate TransferPlayerMoneyTo, and so
-- must this, or the agent gets blueprints for free and is no longer playing
-- the same game. Module blueprints cost the ware's maxprice (the menu's own
-- rule for the module tag; other tags use avgprice * 10).
--
-- Modules only. Every refusal says why in the logbook, so the next cycle can
-- read it.
local function buy_blueprint(args)
    local ware, shipcode = args[1], args[2]
    if not ware or not shipcode then
        log("blueprint needs: blueprint <module ware> <SHIP IDCODE>")
        return false
    end
    local ship = player_ships()[shipcode]
    if not ship then
        log("blueprint: no ship of ours with id code " .. shipcode)
        return false
    end
    local container = C.GetContextByClass(ship, "container", false)
    if container == 0 then
        log("blueprint: " .. shipcode .. " is not docked anywhere")
        return false
    end
    local station = ConvertStringTo64Bit(tostring(container))
    local owner, stationcode = GetComponentData(station, "owner", "idcode")
    if owner == "player" then
        log("blueprint: " .. shipcode .. " is docked at our own " .. tostring(stationcode)
            .. "; blueprints are bought from another faction")
        return false
    end
    if owned_blueprints()[ware] then
        log("blueprint: " .. ware .. " is already ours, not buying it again")
        return false
    end
    if not faction_sells_module(owner, ware) then
        log("blueprint: " .. tostring(owner) .. " does not sell " .. ware)
        return false
    end
    local tradelicence = GetWareData(ware, "tradelicence")
    if not HasLicence("player", tradelicence, owner) then
        log("blueprint: " .. ware .. " needs licence " .. tostring(tradelicence)
            .. " from " .. tostring(owner) .. ", which we do not hold")
        return false
    end
    local price = GetWareData(ware, "maxprice")
    local before = GetPlayerMoney()
    if before < price then
        log(string.format("blueprint: %s costs %d Cr, we have %d", ware, price, before))
        return false
    end
    -- Pay first, then learn, as the menu does.
    TransferPlayerMoneyTo(price, station)
    C.LearnBlueprint(ware)
    log(string.format("ORDER: bought blueprint %s from %s at %s for %d Cr, money %d -> %d, owned now: %s",
                      ware, owner, tostring(stationcode), price, before, GetPlayerMoney(),
                      tostring(owned_blueprints()[ware] == true)))
    return true
end

--- "docked" -> one logbook line per ship of ours docked at another faction's
--- station. That is where a blueprint can be bought (owner's rule), and
--- ships move, so the answer is only good for the moment it is asked.
local function list_docked(args)
    local count = 0
    for code, ship in pairs(player_ships()) do
        local container = C.GetContextByClass(ship, "container", false)
        if container ~= 0 then
            local owner, stationcode = GetComponentData(ConvertStringTo64Bit(tostring(container)),
                                                        "owner", "idcode")
            if owner ~= "player" then
                log(string.format("docked: %s at %s (%s)", code, tostring(stationcode), tostring(owner)))
                count = count + 1
            end
        end
    end
    log("docked: " .. count .. " ship(s) of ours at other factions' stations")
    return true
end

--- "dockat FWR-392 YJA-160 teladi" -> dock and wait at another faction's station.
--
-- Buying a blueprint needs a ship of ours docked where it is sold, and traders
-- only ever dock for moments, so the agent has to be able to send one. This is
-- what the interact menu's "Dock at" does: check the order is allowed and the
-- ship has a pilot, clear its queue, then CreateOrder("DockAndWait") with the
-- station as destination. The faction is passed in because a station of
-- somebody else is found by walking that faction's stations; Python knows the
-- owner from the save. MD cannot do any of this: it cannot take the codes out
-- of the command string.
local function dock_at(args)
    local shipcode, stationcode, faction = args[1], args[2], args[3]
    if not (shipcode and stationcode and faction) then
        log("dockat needs: dockat <SHIP IDCODE> <STATION IDCODE> <faction>")
        return false
    end
    local ship = player_ships()[shipcode]
    if not ship then
        log("dockat: no ship of ours with id code " .. shipcode)
        return false
    end
    local count = C.GetNumAllFactionStations(faction)
    local target
    if count > 0 then
        local buffer = ffi.new("UniverseID[?]", count)
        count = C.GetAllFactionStations(buffer, count, faction)
        for i = 0, count - 1 do
            if ffi.string(C.GetObjectIDCode(buffer[i])) == stationcode then
                target = buffer[i]
                break
            end
        end
    end
    if not target then
        log("dockat: " .. faction .. " has no station " .. stationcode)
        return false
    end
    if not C.IsOrderSelectableFor("DockAndWait", ship) then
        log("dockat: " .. shipcode .. " cannot take a DockAndWait order")
        return false
    end
    local luaship = ConvertStringToLuaID(tostring(ship))
    if not GetComponentData(luaship, "assignedpilot") then
        log("dockat: " .. shipcode .. " has no pilot")
        return false
    end
    C.RemoveAllOrders2(ship, false, false)
    CreateOrder(luaship, "DockAndWait", { destination = ConvertStringToLuaID(tostring(target)) },
                false, false, false)
    log(string.format("ORDER: %s docking at %s (%s)", shipcode, stationcode, faction))
    return true
end

local HANDLERS = {
    price = set_price,
    tradeware = set_tradeware,
    traderule = set_trade_rule,
}

-- Commands that are not about one station. The station handlers above all take
-- an id code as their second word; these do not, so they are dispatched before
-- the station lookup rather than after it.
local GLOBAL_HANDLERS = {
    hostile = set_avoid_hostile,
}

-- Commands with no subject at all: the verb and its own arguments.
local BARE_HANDLERS = {
    blueprint = buy_blueprint,
    docked = list_docked,
    dockat = dock_at,
    savegame = save_agent_slot,
    signals = list_signals,
    respond = set_response,
}

--- Commands arrive as one string, forwarded by MD when it does not recognise
--- them. Shape: "<verb> <STATION IDCODE> <rest...>".
function X4Agent.onCommand(_, command)
    if type(command) ~= "string" then
        return
    end

    local words = {}
    for word in string.gmatch(command, "%S+") do
        words[#words + 1] = word
    end
    local verb, code = words[1], words[2]

    local bare = verb and BARE_HANDLERS[verb]
    if bare then
        local args = {}
        for i = 2, #words do
            args[#args + 1] = words[i]
        end
        local ok, err = pcall(bare, args)
        if not ok then
            log(verb .. " failed: " .. tostring(err))
        end
        return
    end

    -- "avoid hostile on": the second word is the subject, not a station.
    local global_handler = code and GLOBAL_HANDLERS[code]
    if verb == "avoid" and global_handler then
        local args = {}
        for i = 3, #words do
            args[#args + 1] = words[i]
        end
        local ok, err = pcall(global_handler, args)
        if not ok then
            log("avoid failed: " .. tostring(err))
        end
        return
    end

    local handler = verb and HANDLERS[verb]
    if not handler or not code then
        return
    end

    local station = player_stations()[code]
    if not station then
        log(verb .. ": no station of ours with id code " .. code)
        return
    end

    local args = {}
    for i = 3, #words do
        args[#args + 1] = words[i]
    end
    args.code = code

    local ok, err = pcall(handler, station, args)
    if not ok then
        log(verb .. " failed: " .. tostring(err))
    end
end

local initialised = false

-- One handler, whichever copy of this file registered last. The file is loaded
-- twice, through ui.xml and through the MD fallback cue, and each copy has its
-- own locals, so the `initialised` guard alone let both register. Every command
-- then ran twice: harmless for a price, a double payment for anything that
-- buys. Measured 2026-10-18 by tagging each copy (two chunk ids, one command).
-- The handler is kept in a global both copies see, and the old one is taken
-- off before the new one goes on.
local function init()
    if initialised then
        return
    end
    initialised = true
    if _G.__X4AGENT_COMMAND_HANDLER then
        UnregisterEvent("X4Agent.Command", _G.__X4AGENT_COMMAND_HANDLER)
    end
    _G.__X4AGENT_COMMAND_HANDLER = X4Agent.onCommand
    RegisterEvent("X4Agent.Command", X4Agent.onCommand)
    log("ready (chunk " .. CHUNK .. "), handling: price, tradeware, traderule, avoid hostile, signals, respond, savegame, blueprint, docked, dockat")
end

-- Initialise straight away, and do NOT hand this to Register_OnLoad_Init.
--
-- That function looks like the right one: it exists to delay initialisation
-- until the game is loaded, because the C functions do not work before then.
-- But it only appends to a list that the Lua Loader walks once, immediately
-- after it raises its "Ready" signal, and then clears for good. This file is
-- loaded by the MD script *in response to* that same signal, so it arrives a
-- frame too late: the init would be appended to a list nothing will ever
-- iterate again. RegisterEvent would never run, and every command MD forwarded
-- here would be discarded without a sound. That is what happened, undetected,
-- for as long as this file has existed.
--
-- Being loaded after "Ready" is exactly the condition that function waits for,
-- so there is nothing left to wait for. The guard above keeps this harmless if
-- the file is ever loaded twice.
init()

return X4Agent
