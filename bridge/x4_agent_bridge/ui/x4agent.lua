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
declare [[ uint32_t CreateOrder(UniverseID controllableid, const char* orderid, bool defaultorder); ]]
declare [[ bool SetOrderLoop(UniverseID controllableid, size_t orderidx, bool checkonly); ]]
declare [[ int64_t GetBuilderHiringFee(void); ]]
declare [[ bool IsBuilderBusy(UniverseID shipid); ]]
declare [[ uint32_t CreateDeployToStationOrder(UniverseID controllableid); ]]
declare [[ bool RemoveAllOrders(UniverseID controllableid); ]]
declare [[ bool CanContainerBuildShip(UniverseID containerid, UniverseID shipid); ]]
declare [[ void SellPlayerShip(UniverseID shipid, UniverseID shipyardid); ]]
-- 3.6: only functions are declared here. The loadout and crew structures
-- (UILoadout2, CrewTransferInfo2, AddBuildTask6Container) belong to the ship
-- menu and stay its own: a second definition that differs by one field would
-- make the menu's own declaration fail, and that would break the player's
-- ship menu. Their functions are found once that menu has declared them.
declare [[ int64_t GetBuildWarePrice(UniverseID containerid, const char* warename); ]]
-- 3.6: copied from menu_ship_configuration.lua.
declare [[ float GetContainerBuildPriceFactor(UniverseID containerid); ]]
-- 4.9: copied from menu_ship_configuration.lua and menu_map.lua.
declare [[ int64_t GetRepairPrice(UniverseID componenttorepairid, UniverseID containerid); ]]
declare [[ uint32_t GetNumOrders(UniverseID controllableid); ]]
-- 4.3, 4.7, 4.10, 4.12: signatures copied from helper.lua, menu_playerinfo.lua,
-- menu_station_overview.lua, menu_docked.lua and menu_map.lua.
declare [[ void SetContainerBuyLimitOverride(UniverseID containerid, const char* wareid, int32_t amount); ]]
declare [[ void SetContainerSellLimitOverride(UniverseID containerid, const char* wareid, int32_t amount); ]]
declare [[ void ClearContainerBuyLimitOverride(UniverseID containerid, const char* wareid); ]]
declare [[ void ClearContainerSellLimitOverride(UniverseID containerid, const char* wareid); ]]
declare [[ int32_t GetContainerBuyLimit(UniverseID containerid, const char* wareid); ]]
declare [[ int32_t GetContainerSellLimit(UniverseID containerid, const char* wareid); ]]
declare [[ typedef struct { double time; int64_t money; int64_t entryid; const char* eventtype; const char* eventtypename; UniverseID partnerid; const char* partnername; const char* partneridcode; int64_t tradeentryid; const char* tradeeventtype; const char* tradeeventtypename; UniverseID buyerid; UniverseID sellerid; const char* ware; uint32_t amount; int64_t price; bool complete; } TransactionLogEntry; ]]
declare [[ uint32_t GetNumTransactionLog(UniverseID componentid, double starttime, double endtime); ]]
declare [[ double GetCurrentGameTime(void); ]]
declare [[ uint32_t GetAmmoCount(UniverseID defensibleid, const char* macroname); ]]
declare [[ uint32_t GetTransactionLog(TransactionLogEntry* result, uint32_t resultlen, UniverseID componentid, double starttime, double endtime); ]]
declare [[ void SetPlayerGlobalLoadoutLevel(float value); ]]
declare [[ float GetPlayerGlobalLoadoutLevel(void); ]]
declare [[ void SetAllTurretModes(UniverseID defensibleid, const char* mode); ]]
declare [[ typedef struct { float x; float y; float z; float yaw; float pitch; float roll; } UIPosRot; ]]
declare [[ UIPosRot GetObjectPositionInSector(UniverseID objectid); ]]
declare [[ bool IsOrderLoopable(const char* orderdefid); ]]
declare [[ uint32_t GetOrderLoopSkillLimit(); ]]
declare [[ bool EnableOrder(UniverseID controllableid, size_t idx); ]]
declare [[ bool AdjustOrder(UniverseID controllableid, size_t idx, size_t newidx, bool enabled, bool forcestates, bool checkonly); ]]

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
-- Civilian only: traders and miners. Scouts explore hostile space on purpose
-- (the player's decision, 2026-10-21) and fighters go where they are sent.
local BLACKLIST_GROUPS = { "civilian" }

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

--- "avoid hostile on" -> no civilian ship of ours travels through hostile sectors.
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

--- A refusal, in a form the agent reads back from the logbook (memory.py,
--- game_refusals). Confirmations do not carry the marker.
local function refuse(message)
    log("REFUSED: " .. message)
    return false
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
        refuse("blueprint needs: blueprint <module ware> <SHIP IDCODE>")
        return false
    end
    local ship = player_ships()[shipcode]
    if not ship then
        refuse("blueprint: no ship of ours with id code " .. shipcode)
        return false
    end
    local container = C.GetContextByClass(ship, "container", false)
    if container == 0 then
        refuse("blueprint: " .. shipcode .. " is not docked anywhere")
        return false
    end
    local station = ConvertStringTo64Bit(tostring(container))
    local owner, stationcode = GetComponentData(station, "owner", "idcode")
    if owner == "player" then
        refuse("blueprint: " .. shipcode .. " is docked at our own " .. tostring(stationcode)
            .. "; blueprints are bought from another faction")
        return false
    end
    if owned_blueprints()[ware] then
        refuse("blueprint: " .. ware .. " is already ours, not buying it again")
        return false
    end
    if not faction_sells_module(owner, ware) then
        refuse("blueprint: " .. tostring(owner) .. " does not sell " .. ware)
        return false
    end
    local tradelicence = GetWareData(ware, "tradelicence")
    if not HasLicence("player", tradelicence, owner) then
        refuse("blueprint: " .. ware .. " needs licence " .. tostring(tradelicence)
            .. " from " .. tostring(owner) .. ", which we do not hold")
        return false
    end
    local price = GetWareData(ware, "maxprice")
    local before = GetPlayerMoney()
    if before < price then
        refuse(string.format("blueprint: %s costs %d Cr, we have %d", ware, price, before))
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
        refuse("dockat needs: dockat <SHIP IDCODE> <STATION IDCODE> <faction>")
        return false
    end
    local ship = player_ships()[shipcode]
    if not ship then
        refuse("dockat: no ship of ours with id code " .. shipcode)
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
        refuse("dockat: " .. faction .. " has no station " .. stationcode)
        return false
    end
    if not C.IsOrderSelectableFor("DockAndWait", ship) then
        refuse("dockat: " .. shipcode .. " cannot take a DockAndWait order")
        return false
    end
    local luaship = ConvertStringToLuaID(tostring(ship))
    if not GetComponentData(luaship, "assignedpilot") then
        refuse("dockat: " .. shipcode .. " has no pilot")
        return false
    end
    -- A priority order, as the interact menu's priority mode makes it: it runs
    -- now and the ship's own orders stay queued behind it, so `release` hands
    -- the ship back to what it was doing. DockAndWait's timeout defaults to
    -- 0s, which the order defines as infinite: the ship stays until released.
    CreateOrder(luaship, "DockAndWait", { destination = ConvertStringToLuaID(tostring(target)) },
                false, false, true)
    log(string.format("ORDER: %s docking at %s (%s)", shipcode, stationcode, faction))
    return true
end

local ROLE_GROUP = { attack = true, interception = true, defence = true, assist = true }

--- "command NBO-436 JFZ-239 interception" -> put a ship of ours under another
--- ship of ours, in a role. Lua only finds the two ships; MD assigns (see the
--- Agent_Command cues).
local function command_ship(args)
    local shipcode, commandercode, role = args[1], args[2], args[3]
    if not (shipcode and commandercode and role) then
        return refuse("command needs: command <SHIP> <COMMANDER SHIP> <attack|interception|defence|assist>")
    end
    local group = ROLE_GROUP[role]
    if not group then
        return refuse("command: role must be attack, interception, defence or assist, got " .. role)
    end
    local ships = player_ships()
    local ship, commander = ships[shipcode], ships[commandercode]
    if not ship or not commander then
        return refuse("command: both must be ships of ours: " .. shipcode .. ", " .. commandercode)
    end
    if not C.IsOrderSelectableFor("AssignCommander", ship) then
        return refuse("command: " .. shipcode .. " cannot take an AssignCommander order")
    end
    if not GetComponentData(ConvertStringToLuaID(tostring(ship)), "assignedpilot") then
        return refuse("command: " .. shipcode .. " has no pilot")
    end
    -- Hand both over to MD, ship first; MD assigns and logs the result.
    pcall(AddUITriggeredEvent, "X4Agent", "command_ship", ConvertStringToLuaID(tostring(ship)))
    pcall(AddUITriggeredEvent, "X4Agent", "command_" .. role, ConvertStringToLuaID(tostring(commander)))
    return true
end

local function faction_station(faction, stationcode)
    local count = C.GetNumAllFactionStations(faction)
    if count == 0 then
        return nil
    end
    local buffer = ffi.new("UniverseID[?]", count)
    count = C.GetAllFactionStations(buffer, count, faction)
    for i = 0, count - 1 do
        if ffi.string(C.GetObjectIDCode(buffer[i])) == stationcode then
            return buffer[i]
        end
    end
    return nil
end

--- One trade order, as the map menu's buttonConfirmTradeLoop creates it:
--- params 1 ware, 4 location, 5 amount, 7 price threshold in hundredths of a
--- credit (the menu multiplies by 100; tasks/lessons.md L2).
local function trade_order(ship, orderid, ware, location, amount, cents)
    local index = C.CreateOrder(ship, orderid, false)
    if index == 0 then
        return 0
    end
    SetOrderParam(ship, index, 1, nil, ware)
    SetOrderParam(ship, index, 4, nil, ConvertStringToLuaID(tostring(location)))
    SetOrderParam(ship, index, 5, nil, amount)
    SetOrderParam(ship, index, 7, nil, cents)
    C.EnableOrder(ship, index)
    return index
end

--- "haul ASO-629 smartchips JAR-836 argon 200 66 KYV-745" -> buy up to 200
--- smartchips at JAR-836 (argon) for at most 66 Cr each, and bring them to our
--- KYV-745. Two orders the game runs itself: SingleBuy, then SingleSell to our
--- own station at any price, since that money stays with us. The game pays the
--- seller at its own price, never above the cap.
local function haul(args)
    local shipcode, ware, sellercode, faction, amount, cap, homecode =
        args[1], args[2], args[3], args[4], tonumber(args[5]), tonumber(args[6]), args[7]
    if not (shipcode and ware and sellercode and faction and amount and cap and homecode) then
        return refuse("haul needs: haul <SHIP> <ware> <SELLER> <faction> <amount> <max price> <OUR STATION>")
    end
    local ship = player_ships()[shipcode]
    local home = player_stations()[homecode]
    local seller = faction_station(faction, sellercode)
    if not ship then return refuse("haul: no ship of ours with id code " .. shipcode) end
    if not home then return refuse("haul: no station of ours with id code " .. homecode) end
    if not seller then return refuse("haul: " .. faction .. " has no station " .. sellercode) end
    if not GetComponentData(ConvertStringToLuaID(tostring(ship)), "assignedpilot") then
        return refuse("haul: " .. shipcode .. " has no pilot")
    end
    local buy = trade_order(ship, "SingleBuy", ware, seller, amount, math.floor(cap * 100))
    local sell = buy > 0 and trade_order(ship, "SingleSell", ware, home, amount, 0) or 0
    if buy == 0 or sell == 0 then
        return refuse("haul: the game would not create the trade orders for " .. shipcode)
    end
    log(string.format("ORDER: %s hauls up to %d %s from %s (max %d Cr) to %s (orders %d, %d)",
                      shipcode, amount, ware, sellercode, cap, homecode, buy, sell))
    return true
end

--- "loop ASO-629" -> make the ship's order queue repeat. An experiment as
--- much as a verb: the UI's own route goes through a planned default order
--- that could not be traced, so this asks the game what it allows first and
--- logs the answers, then loops from the first order.
local function loop_orders(args)
    local shipcode = args[1]
    local ship = shipcode and player_ships()[shipcode]
    if not ship then
        return refuse("loop needs a ship of ours: loop <SHIP>")
    end
    local can0, can1 = C.SetOrderLoop(ship, 0, true), C.SetOrderLoop(ship, 1, true)
    log(string.format("loop %s: checkonly idx0=%s idx1=%s, loopable SingleBuy=%s, skill limit %d",
                      shipcode, tostring(can0), tostring(can1),
                      tostring(C.IsOrderLoopable("SingleBuy")), C.GetOrderLoopSkillLimit()))
    if not (can1 or can0) then
        return refuse("loop: the game will not loop the orders of " .. shipcode)
    end
    local done = C.SetOrderLoop(ship, can1 and 1 or 0, false)
    log("ORDER: " .. shipcode .. " orders looped from index " .. (can1 and 1 or 0) .. ": " .. tostring(done))
    return true
end

--- "limit KYV-745 energycells sell 5000 raise" -> keep at least 5000 in stock
--- before selling, but only if the manager keeps less; "... clear" -> back to
--- the manager's own. Raise is what the agent sends: a manager can keep far
--- more than the agent would ask for (155,200 energycells on KYV-745 against
--- an asked 1,000), and lowering that sells what the station needs.
local function set_limit(station, args)
    local ware, side, value, mode = args[1], args[2], args[3], args[4]
    if not (ware and (side == "buy" or side == "sell") and value) then
        return refuse("limit needs: limit <STATION> <ware> <buy|sell> <amount|clear>")
    end
    local get = side == "buy" and C.GetContainerBuyLimit or C.GetContainerSellLimit
    local before = get(station, ware)
    if value == "clear" then
        if side == "buy" then C.ClearContainerBuyLimitOverride(station, ware)
        else C.ClearContainerSellLimitOverride(station, ware) end
    else
        local amount = tonumber(value)
        if not amount then
            return refuse("limit: amount must be a number or clear, got " .. value)
        end
        if mode == "raise" and before >= amount then
            log(string.format("limit: %s %s limit for %s is %d already, not lowering to %d",
                              args.code, side, ware, before, amount))
            return true
        end
        if side == "buy" then C.SetContainerBuyLimitOverride(station, ware, amount)
        else C.SetContainerSellLimitOverride(station, ware, amount) end
    end
    log(string.format("ORDER: %s %s limit for %s was %d, asked %s, now %d",
                      args.code, side, ware, before, value, get(station, ware)))
    return true
end

local function station_sector(station)
    return GetComponentData(ConvertStringTo64Bit(tostring(station)), "sectorid")
end

--- "revisit GWH-145 KYV-745" -> the ship revisits the stations it already knows
--- in the sector of our station, refreshing their offers, as its default
--- behaviour. ExploreUpdate stays in known space; Explore went into unknown
--- space and cost five scouts (tasks/lessons.md L18). Parameters as the
--- interact menu's orderExploreUpdate sets them.
local function revisit(args)
    local shipcode, stationcode = args[1], args[2]
    local ship = shipcode and player_ships()[shipcode]
    local station = stationcode and player_stations()[stationcode]
    if not ship or not station then
        return refuse("revisit needs a ship and a station of ours: revisit <SHIP> <STATION>")
    end
    if not C.IsOrderSelectableFor("ExploreUpdate", ship) then
        return refuse("revisit: " .. shipcode .. " cannot take an ExploreUpdate order")
    end
    local sector = station_sector(station)
    CreateOrder(ConvertStringToLuaID(tostring(ship)), "ExploreUpdate",
                { targetspace = sector, destination = { sector, { 0, 0, 0 } } },
                true, false, false, nil, nil, nil, true)
    log(string.format("ORDER: %s revisits known stations around %s", shipcode, stationcode))
    return true
end

--- "satellite TJL-171 JAR-836 argon" -> drop one satellite 3 km from that
--- station (ours when no faction is given). DeployObjectAtPosition as the
--- interact menu builds it. The satellite must be aboard; the game's own
--- resupply buys them at market price.
local function deploy_satellite(args)
    local shipcode, stationcode, faction = args[1], args[2], args[3]
    local ship = shipcode and player_ships()[shipcode]
    local station = stationcode and (faction and faction_station(faction, stationcode)
                                      or player_stations()[stationcode])
    if not ship or not station then
        return refuse("satellite needs: satellite <SHIP> <STATION> [faction]")
    end
    if not C.IsOrderSelectableFor("DeployObjectAtPosition", ship) then
        return refuse("satellite: " .. shipcode .. " cannot take a DeployObjectAtPosition order")
    end
    if C.GetAmmoCount(ship, "eq_arg_satellite_01_macro") == 0 then
        return refuse("satellite: " .. shipcode .. " has no satellite aboard")
    end
    local pos = C.GetObjectPositionInSector(station)
    CreateOrder(ConvertStringToLuaID(tostring(ship)), "DeployObjectAtPosition", {
        destination = { station_sector(station), { pos.x + 3000, pos.y, pos.z } },
        objectstodeploy = "eq_arg_satellite_01_macro",
        amountstodeploy = 1,
    }, false, false, false, nil, nil, nil, true)
    log(string.format("ORDER: %s deploys a satellite near %s", shipcode, stationcode))
    return true
end

local LOADOUT = { off = 0, low = 0.1, medium = 0.5, high = 1.0 }

--- "resupply medium" -> the player's default for automatic resupply of
--- missiles, drones and deployables (menu_playerinfo.lua: 0, 0.1, 0.5, 1.0).
local function set_resupply(args)
    local level = LOADOUT[args[1] or ""]
    if not level then
        return refuse("resupply needs: resupply <off|low|medium|high>")
    end
    local before = C.GetPlayerGlobalLoadoutLevel()
    C.SetPlayerGlobalLoadoutLevel(level)
    log(string.format("ORDER: resupply level was %.2f, now %.2f", before, C.GetPlayerGlobalLoadoutLevel()))
    return true
end

local TURRET_MODES = { defend = true, attackenemies = true, attackcapital = true,
                       attackfighters = true, missiledefence = true }

--- "turrets KYV-745 attackenemies" -> every turret on the station in one mode.
local function set_turrets(station, args)
    local mode = args[1]
    if not TURRET_MODES[mode or ""] then
        return refuse("turrets needs: turrets <STATION> <defend|attackenemies|attackcapital|attackfighters|missiledefence>")
    end
    C.SetAllTurretModes(station, mode)
    log(string.format("ORDER: turrets on %s set to %s", args.code, mode))
    return true
end

--- "ledger 2" -> per station of ours, what it paid other factions in the last
--- 2 hours, per ware, from the game's transaction log. The save's own trade
--- log has no counterparty, so this is the only way to see money leaking to
--- NPC sellers for wares our own ships could have delivered.
local function ledger(args)
    local hours = tonumber(args[1] or "2") or 2
    local now = C.GetCurrentGameTime()
    for code, station in pairs(player_stations()) do
        local count = C.GetNumTransactionLog(station, now - hours * 3600, now)
        local paid, total = {}, 0
        if count > 0 then
            local buffer = ffi.new("TransactionLogEntry[?]", count)
            count = C.GetTransactionLog(buffer, count, station, now - hours * 3600, now)
            for i = 0, count - 1 do
                local e = buffer[i]
                if e.buyerid == station and e.sellerid ~= 0 then
                    local owner = GetComponentData(ConvertStringTo64Bit(tostring(e.sellerid)), "owner")
                    if owner and owner ~= "player" then
                        local ware = ffi.string(e.ware)
                        local cr = tonumber(e.price) * e.amount / 100
                        paid[ware] = (paid[ware] or 0) + cr
                        total = total + cr
                    end
                end
            end
        end
        local parts = {}
        for ware, cr in pairs(paid) do
            parts[#parts + 1] = string.format("%s=%d", ware, cr)
        end
        table.sort(parts)
        log(string.format("LEDGER %s %dh paid_to_npcs=%d %s", code, hours, total, table.concat(parts, " ")))
    end
    return true
end

--- "repair NBO-436 SHY-001 argon" -> fly to a shipyard and repair there, paid.
--- The Repair order does not charge a ship of ours: in order.repair.xml the
--- transfer for player-owned ships is commented out, because the ship menu
--- takes the money up front with the rest of its shopping list and puts the
--- price in the order as its accepted cost. Two repairs went unpaid that way
--- (KGZ-352 and FWR-392, 2026-10-18/19) before this paid like the menu: the
--- hull at that yard's GetRepairPrice, no discount, before the order exists,
--- refunded if no order appears.
local function repair(args)
    local shipcode, yardcode, faction = args[1], args[2], args[3]
    local ship = shipcode and player_ships()[shipcode]
    local yard = yardcode and faction and faction_station(faction, yardcode)
    if not ship or not yard then
        return refuse("repair needs: repair <SHIP> <SHIPYARD> <faction>")
    end
    if not C.IsOrderSelectableFor("Repair", ship) then
        return refuse("repair: " .. shipcode .. " cannot take a Repair order")
    end
    local price = tonumber(C.GetRepairPrice(ship, yard))
    if not price or price <= 0 then
        return refuse("repair: " .. shipcode .. " has no hull damage to repair at " .. yardcode)
    end
    local before = GetPlayerMoney()
    if before < price then
        return refuse(string.format("repair: %s costs %d Cr at %s, we have %d", shipcode, price, yardcode, before))
    end
    local y64 = ConvertStringTo64Bit(tostring(yard))
    local queued = C.GetNumOrders(ship)
    TransferPlayerMoneyTo(price, y64)
    -- As the ship menu fills it (processRepairsFor): destination, hull to
    -- 100 percent, no single components, not repairall, and the price as the
    -- accepted cost. With only a destination the order found nothing to
    -- repair and ended at once. A priority order: queued normally it waited
    -- behind fourteen trade orders (FWR-392, 2026-10-18). Its own orders
    -- resume after the repair.
    local ok, err = pcall(CreateOrder, ConvertStringToLuaID(tostring(ship)), "Repair",
                          { destination = ConvertStringToLuaID(tostring(yard)), hullpercent = 100,
                            damagedcomponents = {}, repairall = false, acceptedcost = price },
                          false, false, true)
    if not ok or C.GetNumOrders(ship) <= queued then
        TransferMoneyToPlayer(price, y64, "refund")
        return refuse(string.format("repair: no Repair order for %s; %d Cr refunded%s",
                                    shipcode, price, ok and "" or (": " .. tostring(err))))
    end
    log(string.format("ORDER: %s goes to %s for repair, paid %d Cr, money %d -> %d",
                      shipcode, yardcode, price, before, GetPlayerMoney()))
    return true
end

--- "patrol NBO-436 KYV-745" -> patrol the sector our station is in, as its
--- default behaviour (order.fight.patrol.xml: space, pursuetargets).
local function patrol(args)
    local shipcode, stationcode = args[1], args[2]
    local ship = shipcode and player_ships()[shipcode]
    local station = stationcode and player_stations()[stationcode]
    if not ship or not station then
        return refuse("patrol needs a ship and a station of ours: patrol <SHIP> <STATION>")
    end
    if not C.IsOrderSelectableFor("Patrol", ship) then
        return refuse("patrol: " .. shipcode .. " cannot take a Patrol order")
    end
    CreateOrder(ConvertStringToLuaID(tostring(ship)), "Patrol",
                { space = station_sector(station), pursuetargets = true }, true, false, false)
    log(string.format("ORDER: %s patrols around %s", shipcode, stationcode))
    return true
end

--- "findbuilds XYZ-123" -> a construction vessel of ours looks for our builds
--- itself (order.build.find.task.xml; playeronly is the default for ours).
local function find_builds(args)
    local ship = args[1] and player_ships()[args[1]]
    if not ship then
        return refuse("findbuilds needs a ship of ours: findbuilds <SHIP>")
    end
    if not C.IsOrderSelectableFor("FindBuildTasks", ship) then
        return refuse("findbuilds: " .. args[1] .. " cannot take a FindBuildTasks order")
    end
    CreateOrder(ConvertStringToLuaID(tostring(ship)), "FindBuildTasks", {}, true, false, false)
    log("ORDER: " .. args[1] .. " looks for our build tasks")
    return true
end

local function faction_ship(faction, shipcode)
    local count = C.GetNumAllFactionShips(faction)
    if count == 0 then
        return nil
    end
    local buffer = ffi.new("UniverseID[?]", count)
    count = C.GetAllFactionShips(buffer, count, faction)
    for i = 0, count - 1 do
        if ffi.string(C.GetObjectIDCode(buffer[i])) == shipcode then
            return buffer[i]
        end
    end
    return nil
end

--- "hire CZK-784 antigone KYV-745" -> hire somebody else's construction vessel
--- for the build at our station. The map menu's selectCV, step by step: not
--- busy, not an enemy, pay GetBuilderHiringFee to the vessel, then clear its
--- orders and give it a DeployToStation order to our station.
local function hire_builder(args)
    local buildercode, faction, stationcode = args[1], args[2], args[3]
    if not (buildercode and faction and stationcode) then
        return refuse("hire needs: hire <BUILDER> <faction> <OUR STATION>")
    end
    local builder = faction_ship(faction, buildercode)
    local station = player_stations()[stationcode]
    if not builder then return refuse("hire: " .. faction .. " has no ship " .. buildercode) end
    if not station then return refuse("hire: no station of ours with id code " .. stationcode) end
    local b64 = ConvertStringTo64Bit(tostring(builder))
    local isenemy = GetComponentData(b64, "isreallyenemy")
    if C.IsBuilderBusy(builder) or isenemy then
        return refuse("hire: " .. buildercode .. " is busy or hostile")
    end
    if not C.IsOrderSelectableFor("DeployToStation", builder) then
        return refuse("hire: " .. buildercode .. " cannot take a DeployToStation order")
    end
    local fee = tonumber(C.GetBuilderHiringFee())
    local before = GetPlayerMoney()
    if before < fee then
        return refuse(string.format("hire: the fee is %d Cr, we have %d", fee, before))
    end
    TransferPlayerMoneyTo(fee, b64)
    C.RemoveAllOrders(builder)
    local index = C.CreateDeployToStationOrder(builder)
    if index > 0 then
        SetOrderParam(ConvertStringToLuaID(tostring(builder)), index, 1, nil,
                      ConvertStringToLuaID(tostring(station)))
        C.EnableOrder(builder, index)
    end
    log(string.format("ORDER: hired %s (%s) for %s, fee %d Cr, money %d -> %d, order %d",
                      buildercode, faction, stationcode, fee, before, GetPlayerMoney(), index))
    return true
end

--- "deploy BLD-001 KYV-745" -> a construction vessel of ours builds at our
--- station: the map menu's selectCV for a vessel of ours, which is the hire
--- above without a fee. Not when it is busy on another build of ours.
local function deploy_builder(args)
    local shipcode, stationcode = args[1], args[2]
    if not (shipcode and stationcode) then
        return refuse("deploy needs: deploy <OUR BUILDER> <OUR STATION>")
    end
    local builder = player_ships()[shipcode]
    local station = player_stations()[stationcode]
    if not builder then return refuse("deploy: no ship of ours with id code " .. shipcode) end
    if not station then return refuse("deploy: no station of ours with id code " .. stationcode) end
    if C.IsBuilderBusy(builder) then
        return refuse("deploy: " .. shipcode .. " is busy with another build")
    end
    if not C.IsOrderSelectableFor("DeployToStation", builder) then
        return refuse("deploy: " .. shipcode .. " cannot take a DeployToStation order")
    end
    C.RemoveAllOrders(builder)
    local index = C.CreateDeployToStationOrder(builder)
    if index > 0 then
        SetOrderParam(ConvertStringToLuaID(tostring(builder)), index, 1, nil,
                      ConvertStringToLuaID(tostring(station)))
        C.EnableOrder(builder, index)
    end
    log(string.format("ORDER: %s deploys to %s, order %d", shipcode, stationcode, index))
    return true
end

--- "manager GKL-870" -> one of our crew runs the station: the personnel menu's
--- "work somewhere else" to the manager post (menu_map.lua, the crew transfer
--- to a station), for the person on any ship of ours whose combined skill for
--- that post is highest. No fee, as in the game: the crew came with the ships
--- we paid for. The person travels there; the save names them on arrival.
--- The types and functions are the map menu's, used once it has declared them.
local function assign_manager(station, args)
    if GetComponentData(ConvertStringTo64Bit(tostring(station)), "tradenpc") then
        return refuse("manager: " .. args.code .. " has a manager")
    end
    local okfn, can = pcall(function() return C.CanControllableHaveControlEntity(station, "manager") end)
    if not okfn then
        return refuse("manager: the map menu's functions are not available: " .. tostring(can))
    end
    if not can then
        return refuse("manager: " .. args.code .. " cannot have a manager")
    end
    local candidates = {}
    for shipcode, ship in pairs(player_ships()) do
        local n = C.GetNumAllRoles()
        local people = ffi.new("PeopleInfo[?]", n)
        n = C.GetPeople2(people, n, ship, false)
        for i = 0, n - 1 do
            local role = ffi.string(people[i].id)
            if (role == "service" or role == "marine") and people[i].amount > 0 then
                local ntiers = people[i].numtiers
                local tiers = ffi.new("RoleTierData[?]", ntiers)
                ntiers = C.GetRoleTiers(tiers, ntiers, ship, role)
                for j = 0, ntiers - 1 do
                    local count = tiers[j].amount
                    if count > 0 then
                        local seeds = ffi.new("NPCSeed[?]", count)
                        count = C.GetRoleTierNPCs(seeds, count, ship, role, tiers[j].skilllevel)
                        for k = 0, count - 1 do
                            candidates[#candidates + 1] = {
                                ship = ship, shipcode = shipcode, seed = seeds[k],
                                skill = C.GetPersonCombinedSkill(ship, seeds[k], nil, "manager") }
                        end
                    end
                end
            end
        end
    end
    table.sort(candidates, function(a, b) return a.skill > b.skill end)
    local tally = {}
    for _, c in ipairs(candidates) do
        local actor = { entity = nil, personcontrollable = c.ship, personseed = c.seed }
        local reason = ffi.string(C.AssignHiredActor(actor, station, "manager", nil, true))
        if reason == "" then
            C.AssignHiredActor(actor, station, "manager", nil, false)
            log(string.format("ORDER: crew from %s sent to manage %s, manager skill %d of 100",
                              c.shipcode, args.code, c.skill))
            return true
        end
        tally[reason] = (tally[reason] or 0) + 1
    end
    local parts = {}
    for reason, n in pairs(tally) do
        parts[#parts + 1] = reason .. " " .. n
    end
    -- "invalid" for every candidate while the station is still being built:
    -- nobody can be sent to a construction site.
    return refuse(string.format("manager: nobody of ours can take %s: %d candidates (%s)",
                                args.code, #candidates, table.concat(parts, ", ")))
end

--- "account GKL-870" -> the station account set to what the game recommends:
--- the map menu's "Accept Estimate" (infoSubmenuSetManagerAccountToEstimate).
--- The estimate is the game's own: productionmoney plus the supply and trade
--- ware budgets. Min becomes the estimate, max half as much again, and what is
--- missing moves from the player. `budget` sets min and max only, so a
--- station with no sales of its own kept an empty account and bought nothing.
--- Only tops up: a station holding more keeps it.
local function set_account(station, args)
    local s64 = ConvertStringTo64Bit(tostring(station))
    local money, estimate = GetComponentData(s64, "money", "productionmoney")
    local okextra, extra = pcall(function()
        return tonumber(C.GetSupplyBudget(station)) / 100 + tonumber(C.GetTradeWareBudget(station)) / 100
    end)
    if not okextra then
        return refuse("account: the map menu's functions are not available: " .. tostring(extra))
    end
    estimate = (estimate or 0) + extra
    money = money or 0
    if estimate <= 0 then
        return refuse("account: the game recommends nothing for " .. args.code)
    end
    local amount = estimate - money
    if amount > 0 and amount > GetPlayerMoney() then
        return refuse(string.format("account: %s needs %d Cr, we have %d", args.code, amount, GetPlayerMoney()))
    end
    SetMaxBudget(s64, (estimate * 3) / 2)
    SetMinBudget(s64, estimate)
    if amount > 0 then
        TransferPlayerMoneyTo(amount, s64)
    end
    log(string.format("ORDER: account of %s set to the estimate %d Cr, %d Cr moved from the player",
                      args.code, estimate, math.max(amount, 0)))
    return true
end

--- "buildfund KYV-745" -> the station's build storage gets what the game says
--- its builds still need: the Plan Build menu's construction money set to the
--- estimate (menu_station_configuration.lua buttonConfirmMoney, with the map
--- menu's "wantedmoney" estimate). Only tops up. `fund` moved a share of the
--- player's money instead: 4.7 million for a dock of about 0.4.
local function fund_build(station, args)
    local bsid = GetComponentData(ConvertStringTo64Bit(tostring(station)), "buildstorage")
    if not bsid or bsid == 0 then
        return refuse("buildfund: " .. args.code .. " has no build storage")
    end
    local bs = ConvertStringTo64Bit(tostring(ConvertIDTo64Bit(bsid)))
    local money, wanted = GetComponentData(bs, "money", "wantedmoney")
    money, wanted = money or 0, wanted or 0
    local amount = wanted - money
    if amount <= 0 then
        return refuse(string.format("buildfund: %s has %d Cr, its builds want %d", args.code, money, wanted))
    end
    if amount > GetPlayerMoney() then
        return refuse(string.format("buildfund: %s wants %d Cr, we have %d", args.code, amount, GetPlayerMoney()))
    end
    TransferPlayerMoneyTo(amount, bs)
    log(string.format("ORDER: build storage of %s funded with %d Cr, as the build wants %d",
                      args.code, amount, wanted))
    return true
end

--- "cancelbuild KYV-745 refinedmetals" -> the station's queued builds are
--- cancelled where the game allows it: the interact menu's "Cancel
--- construction" (CancelConstruction after CanCancelConstruction). Python
--- sends it only for queued builds whose modules all stand already
--- (executor._adds_nothing). The refusal names the ware, so the expansion
--- that made the empty build is not asked for again (executor._expansion_refused).
local function cancel_build(station, args)
    local ware = args[1] or "unknown"
    local containers = { station }
    local bsid = GetComponentData(ConvertStringTo64Bit(tostring(station)), "buildstorage")
    if bsid and bsid ~= 0 then
        containers[#containers + 1] = ConvertIDTo64Bit(bsid)
    end
    local ok, cancelled = pcall(function()
        local count = 0
        for _, container in ipairs(containers) do
            local n = C.GetNumBuildTasks(container, 0, false, false)
            if n > 0 then
                local buf = ffi.new("BuildTaskInfo[?]", n)
                n = C.GetBuildTasks(buf, n, container, 0, false, false)
                for i = 0, n - 1 do
                    if C.CanCancelConstruction(container, buf[i].id) then
                        C.CancelConstruction(container, buf[i].id)
                        count = count + 1
                    end
                end
            end
        end
        return count
    end)
    if not ok then
        return refuse("cancelbuild: the map menu's functions are not available: " .. tostring(cancelled))
    end
    if cancelled == 0 then
        return refuse("cancelbuild: no queued build of " .. args.code .. " could be cancelled")
    end
    log(string.format("ORDER: %d queued build(s) of %s cancelled", cancelled, args.code))
    return refuse(string.format("%s: could not build a construction sequence that adds anything (%s)",
                                args.code, ware))
end

--- "plot GKL-870 3 2000000" -> the station's plot grown to 3 km a side, both
--- ways along each axis, at the Plan Build menu's price and not above the
--- given cap: ExtendBuildPlot, the price GetBuildPlotPrice for the new size
--- less what was paid (GetBuildPlotPayment), paid to the sector's control
--- station, then PayBuildPlotSize (menu_station_configuration.lua). Free
--- outside owned space, as there. A price above the cap is refused, naming it.
local function extend_plot(station, args)
    local km, cap = tonumber(args[1]), tonumber(args[2])
    if not (km and cap) or km < 1 or km > 20 then
        return refuse("plot needs: plot <OUR STATION> <km a side, 1 to 20> <max price>")
    end
    if not (Helper and Helper.getPlotData) then
        return refuse("plot: the menu helpers are not loaded")
    end
    local ok, data = pcall(Helper.getPlotData, station)
    if not ok then
        return refuse("plot: no plot data for " .. args.code .. ": " .. tostring(data))
    end
    local pos, neg = { x = 0, y = 0, z = 0 }, { x = 0, y = 0, z = 0 }
    local new = {}
    for _, axis in ipairs({ "x", "y", "z" }) do
        local more = km - data.size[axis]
        if more > 0 then
            pos[axis] = math.ceil(more / 2) * 1000
            neg[axis] = math.floor(more / 2) * 1000
        end
        new[axis] = data.size[axis] * 1000 + pos[axis] + neg[axis]
    end
    if pos.x + pos.y + pos.z == 0 then
        return refuse(string.format("plot: %s is %g by %g by %g km already", args.code,
                                    data.size.x, data.size.y, data.size.z))
    end
    local price = 0
    if data.isinownedspace then
        local buf = ffi.new("bool[1]", 0)
        price = tonumber(C.GetBuildPlotPrice(data.sector, data.position, new.x, new.y, new.z, "player"))
            - tonumber(C.GetBuildPlotPayment(station, buf))
    end
    if price > cap or price > GetPlayerMoney() then
        return refuse(string.format("plot: %s to %d km costs %d Cr, cap %d, we have %d",
                                    args.code, km, price, cap, GetPlayerMoney()))
    end
    if not C.ExtendBuildPlot(station, pos, neg, false) then
        return refuse("plot: the game would not extend the plot of " .. args.code)
    end
    if price > 0 then
        TransferPlayerMoneyTo(price, ConvertStringTo64Bit(tostring(C.GetSectorControlStation(data.sector))))
    end
    C.PayBuildPlotSize(station, C.GetBuildPlotSize(station), C.GetBuildPlotCenterOffset(station))
    log(string.format("ORDER: plot of %s extended to %d km, %d Cr paid", args.code, km, price))
    return true
end

--- "sellship ASO-629 WRF-001 argon" -> sell a ship of ours at that shipyard,
--- for what the game says it is worth there. The map menu's sell dialog:
--- the ship must be sellable and the yard able to build it; the value is
--- GetTotalValue, the player is paid with TransferMoneyToPlayer, then
--- SellPlayerShip hands the ship over.
local function sell_ship(args)
    local shipcode, yardcode, faction = args[1], args[2], args[3]
    local ship = shipcode and player_ships()[shipcode]
    local yard = yardcode and faction and faction_station(faction, yardcode)
    if not ship or not yard then
        return refuse("sellship needs: sellship <SHIP> <SHIPYARD> <faction>")
    end
    local s64 = ConvertStringTo64Bit(tostring(ship))
    if not GetComponentData(s64, "issellable") then
        return refuse("sellship: " .. shipcode .. " cannot be sold")
    end
    if not C.CanContainerBuildShip(yard, ship) then
        return refuse("sellship: " .. yardcode .. " does not take ships like " .. shipcode)
    end
    local y64 = ConvertStringTo64Bit(tostring(yard))
    local price = GetTotalValue(s64, true, y64)
    local before = GetPlayerMoney()
    TransferMoneyToPlayer(price, y64, "sellship")
    C.SellPlayerShip(ship, yard)
    log(string.format("ORDER: sold %s at %s for %d Cr, money %d -> %d",
                      shipcode, yardcode, price, before, GetPlayerMoney()))
    return true
end

--- What a generated loadout costs at this wharf, priced the way the ship
--- menu prices it (menu.insertWare) but without its discounts, so the agent
--- never pays less than the menu would ask: equipment at the wharf's build
--- price, nothing for a volatile ware, and software at the wharf's own ware
--- price times its build price factor. Software at the build price had come
--- out at about 25,000 Cr where the menu asks 168,849, and a Mercury cost
--- 931,976 against the menu's 1,075,854 for the same parts (2026-10-19).
--- Field names as UILoadout2 declares them.
local function loadout_price(wharf, loadout)
    local total = 0
    local function add(macro, n)
        if macro and macro ~= "" then
            local ware = GetMacroData(macro, "ware")
            if ware and ware ~= "" and not GetWareData(ware, "volatile") then
                total = total + tonumber(C.GetBuildWarePrice(wharf, ware)) * (n or 1)
            end
        end
    end
    for _, field in ipairs({ "weapons", "turrets", "shields", "engines" }) do
        for i = 0, (loadout["num" .. field] or 0) - 1 do
            add(ffi.string(loadout[field][i].macro), 1)
        end
    end
    for _, field in ipairs({ "turretgroups", "shieldgroups" }) do
        for i = 0, (loadout["num" .. field] or 0) - 1 do
            add(ffi.string(loadout[field][i].macro), loadout[field][i].count)
        end
    end
    for _, field in ipairs({ "ammo", "units" }) do
        for i = 0, (loadout["num" .. field] or 0) - 1 do
            add(ffi.string(loadout[field][i].macro), loadout[field][i].amount)
        end
    end
    local factor = tonumber(C.GetContainerBuildPriceFactor(wharf))
    local w64 = ConvertStringTo64Bit(tostring(wharf))
    for i = 0, (loadout.numsoftware or 0) - 1 do
        local ware = ffi.string(loadout.software[i].ware)
        if ware ~= "" then
            total = total + factor * GetContainerWarePrice(w64, ware, false)
        end
    end
    if loadout.thruster.macro ~= nil then
        add(ffi.string(loadout.thruster.macro), 1)
    end
    return math.ceil(total)
end

--- "buyship WRF-001 argon ship_arg_s_scout_01_a_macro x4-agent-scout 300000"
--- -> build that ship at that wharf, with the game's generated loadout at a
--- medium level, for at most 300,000 Cr. The engine does not take the money
--- for a build task (docs/roadmap.md); the ship menu pays with
--- TransferPlayerMoneyTo and records it with SetBuildTaskTransferredMoney, and
--- so does this, before the task exists. A task the engine refuses is refunded.
local function buy_ship(args)
    local wharfcode, faction, macro, name, cap = args[1], args[2], args[3], args[4], tonumber(args[5])
    if not (wharfcode and faction and macro and name and cap) then
        return refuse("buyship needs: buyship <WHARF> <faction> <macro> <name> <max spend>")
    end
    local wharf = faction_station(faction, wharfcode)
    if not wharf then
        return refuse("buyship: " .. faction .. " has no station " .. wharfcode)
    end
    local shipware = GetMacroData(macro, "ware")
    if not shipware or shipware == "" then
        return refuse("buyship: " .. macro .. " is not a ship that is sold")
    end
    if not (Helper and Helper.getLoadoutHelper2) then
        return refuse("buyship: the menu helpers are not loaded")
    end
    local ok, loadout = pcall(Helper.getLoadoutHelper2, C.GenerateShipLoadout2,
                              C.GenerateShipLoadoutCounts2, "UILoadout2", wharf, 0, macro, 0.5)
    if not ok then
        return refuse("buyship: no loadout for " .. macro .. ": " .. tostring(loadout))
    end
    -- Everything that can fail happens before any money moves.
    local okprice, partprice = pcall(loadout_price, wharf, loadout)
    if not okprice then
        return refuse("buyship: could not price the loadout: " .. tostring(partprice))
    end
    local okstructs, crew, info = pcall(function()
        return ffi.new("CrewTransferInfo2"), ffi.new("AddBuildTask6Container")
    end)
    if not okstructs then
        return refuse("buyship: the ship menu's types are not available: " .. tostring(crew))
    end
    local price = tonumber(C.GetBuildWarePrice(wharf, shipware)) + partprice
    local before = GetPlayerMoney()
    if price > cap then
        return refuse(string.format("buyship: %s costs %d Cr at %s, above the cap of %d", macro, price, wharfcode, cap))
    end
    if before < price then
        return refuse(string.format("buyship: %s costs %d Cr, we have %d", macro, price, before))
    end
    local w64 = ConvertStringTo64Bit(tostring(wharf))
    TransferPlayerMoneyTo(price, w64)
    local oktask, task = pcall(C.AddBuildTask6, wharf, 0, macro, loadout, price, crew, false, name, info)
    if not oktask then
        TransferMoneyToPlayer(price, w64, "refund")
        return refuse("buyship: AddBuildTask6 failed, " .. price .. " Cr refunded: " .. tostring(task))
    end
    if task == 0 then
        TransferMoneyToPlayer(price, w64, "refund")
        return refuse(string.format("buyship: %s would not build %s; %d Cr refunded", wharfcode, macro, price))
    end
    C.SetBuildTaskTransferredMoney(task, price)
    log(string.format("ORDER: bought %s at %s as %s for %d Cr, money %d -> %d, task %s",
                      macro, wharfcode, name, price, before, GetPlayerMoney(), tostring(task)))
    return true
end

--- "panel clear" / "panel <text>" -> one line of the in-game panel (3.9).
--- MD keeps the list and renders it; this only takes the string apart.
local function panel(args)
    if args[1] == "clear" and #args == 1 then
        pcall(AddUITriggeredEvent, "X4Agent", "panelclear", "")
        return true
    end
    pcall(AddUITriggeredEvent, "X4Agent", "panel", table.concat(args, " "))
    return true
end

--- "licence tradesubscription TJL-171" -> buy a licence, paid, at the faction
--- whose station the ship is docked at.
--
-- The licence tab of the same menu as blueprints: GetOwnLicences(faction)
-- lists what the faction offers with its price, minrelation (UI scale, which
-- is what GetUIRelation returns) and precursor; the menu refuses below the
-- reputation or without the precursor, and only offers what issellable says.
-- Most licences are not for sale at all: they come with a promotion ceremony.
local function buy_licence(args)
    local kind, shipcode = args[1], args[2]
    if not kind or not shipcode then
        return refuse("licence needs: licence <type> <SHIP IDCODE>")
    end
    local ship = player_ships()[shipcode]
    if not ship then
        return refuse("licence: no ship of ours with id code " .. shipcode)
    end
    local container = C.GetContextByClass(ship, "container", false)
    if container == 0 then
        return refuse("licence: " .. shipcode .. " is not docked anywhere")
    end
    local station = ConvertStringTo64Bit(tostring(container))
    local owner, stationcode = GetComponentData(station, "owner", "idcode")
    if owner == "player" then
        return refuse("licence: " .. shipcode .. " is docked at our own " .. tostring(stationcode))
    end
    if HasLicence("player", kind, owner) then
        return refuse("licence: " .. kind .. " from " .. owner .. " is already ours")
    end
    local offer
    for _, licence in ipairs(GetOwnLicences(owner) or {}) do
        if licence.type == kind then
            offer = licence
            break
        end
    end
    if not offer or not offer.issellable then
        return refuse("licence: " .. owner .. " does not sell " .. kind)
    end
    local standing = GetUIRelation(owner)
    if offer.minrelation > standing then
        return refuse(string.format("licence: %s from %s needs reputation %s, we stand at %s",
                                    kind, owner, tostring(offer.minrelation), tostring(standing)))
    end
    if offer.precursor ~= nil and not HasLicence("player", offer.precursor, owner) then
        return refuse("licence: " .. kind .. " from " .. owner .. " needs " .. offer.precursor .. " first")
    end
    local before = GetPlayerMoney()
    if before < offer.price then
        return refuse(string.format("licence: %s costs %d Cr, we have %d", kind, offer.price, before))
    end
    TransferPlayerMoneyTo(offer.price, station)
    AddLicence("player", kind, owner)
    log(string.format("ORDER: bought licence %s from %s at %s for %d Cr, money %d -> %d, held now: %s",
                      kind, owner, tostring(stationcode), offer.price, before, GetPlayerMoney(),
                      tostring(HasLicence("player", kind, owner))))
    return true
end

--- "release FWR-392" -> take away the agent's priority orders (DockAndWait),
--- so the ship goes back to its own queue and default behaviour.
local function release(args)
    local shipcode = args[1]
    if not shipcode then
        return refuse("release needs: release <SHIP IDCODE>")
    end
    local ship = player_ships()[shipcode]
    if not ship then
        return refuse("release: no ship of ours with id code " .. shipcode)
    end
    C.RemoveAllOrders2(ship, false, true)
    log("ORDER: " .. shipcode .. " released")
    return true
end

local HANDLERS = {
    limit = set_limit,
    turrets = set_turrets,
    price = set_price,
    tradeware = set_tradeware,
    traderule = set_trade_rule,
    manager = assign_manager,
    account = set_account,
    buildfund = fund_build,
    plot = extend_plot,
    cancelbuild = cancel_build,
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
    release = release,
    licence = buy_licence,
    command = command_ship,
    haul = haul,
    loop = loop_orders,
    revisit = revisit,
    satellite = deploy_satellite,
    resupply = set_resupply,
    ledger = ledger,
    repair = repair,
    patrol = patrol,
    findbuilds = find_builds,
    hire = hire_builder,
    deploy = deploy_builder,
    panel = panel,
    sellship = sell_ship,
    buyship = buy_ship,
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
    log("ready (chunk " .. CHUNK .. "), handling: price, tradeware, traderule, avoid hostile, signals, respond, savegame, blueprint, docked, dockat, release, licence, command, haul, loop, limit, turrets, revisit, satellite, resupply, ledger, repair, patrol, findbuilds, hire, deploy, panel, sellship, buyship")
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
