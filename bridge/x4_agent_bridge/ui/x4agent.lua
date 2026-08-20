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

local HANDLERS = {
    price = set_price,
    tradeware = set_tradeware,
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
    log("ready, handling: price, tradeware")
end

-- Register_OnLoad_Init comes from the Lua Loader API, and delays this until the
-- game is actually loaded. Calling the C functions any earlier does not work.
if Register_OnLoad_Init then
    Register_OnLoad_Init(init, "extensions.x4_agent_bridge.ui.x4agent")
else
    init()
end

return X4Agent
