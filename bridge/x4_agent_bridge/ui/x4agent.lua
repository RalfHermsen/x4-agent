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
declare [[ void SetContainerGlobalPriceFactor(UniverseID containerid, float value); ]]
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

local X4Agent = {}

local function log(message)
    DebugError("[x4-agent lua] " .. tostring(message))
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
-- happened to a warehouse full of sunriseflowers. Setting an override also
-- clears the global price factor, because that is what the station
-- configuration menu does when you move a per-ware slider.
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
    SetContainerWarePriceOverride(station, ware, side == "buy", value)
    C.SetContainerGlobalPriceFactor(station, -1)
    log(string.format("price override on %s: %s %s = %d", args.code, ware, side, value))
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
    log(string.format("%s: %s %s is now %s", args.code, side,
                      (ware == "") and "everything" or ware, mode))
    return true
end

local HANDLERS = {
    price = set_price,
    tradeware = set_tradeware,
    traderule = set_trade_rule,
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

local function init()
    RegisterEvent("X4Agent.Command", X4Agent.onCommand)
    log("ready, handling: price, tradeware, traderule")
end

-- Register_OnLoad_Init comes from the Lua Loader API, and delays this until the
-- game is actually loaded. Calling the C functions any earlier does not work.
if Register_OnLoad_Init then
    Register_OnLoad_Init(init, "extensions.x4_agent_bridge.ui.x4agent")
else
    init()
end

return X4Agent
