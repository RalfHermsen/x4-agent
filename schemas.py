"""The two core contracts between executor and planner (local LLM).

    Sitrep          : the compressed game state that goes TO the model.
    PlannerResponse : the structured decision the model gives BACK.

Design principles
-----------------
1. Token efficiency. Storage as a fraction (0-1) plus 'starved' flags, not raw
   unit counts. Fleets aggregated per role, not per ship. The executor
   pre-computes opportunities (top-N) instead of dumping the whole market. Cap
   how many detailed stations and opportunities you send (guideline: <=25
   stations, <=15 opportunities), or the model drowns and the cost climbs.

2. The planner/executor boundary. The executor supplies `derived_phase`,
   `opportunities` (with an estimated value) and `spend_cap_remaining`. The
   model CHOOSES and prioritises; it does not compute routes or prices from raw
   data.

3. Guardrails, doubly enforced. The sitrep carries `spend_cap_remaining`; the
   planner may not emit actions that together exceed it. Every spending action
   additionally carries its own `max_spend`, which the executor enforces hard,
   regardless of what the model says.

4. Memory loop. `active_goals` goes IN (from the store of previous cycles);
   `updated_goals` comes OUT and is stored again. That keeps the agent
   strategically coherent across cycles instead of planning from zero each time.

Phase usage
-----------
Phase 1 (read-only advisor): PlannerResponse.actions are ADVICE; the executor
runs nothing and only logs. Phase 2 and beyond: the executor actually performs a
growing subset of the action types through the named pipes and MD bridge.

Prompt integration
------------------
Validate the LLM response with `PlannerResponse.model_validate_json(...)` and
re-prompt on failure. Pydantic v2.

Note (measured 2026-08-19): Ollama enforces the schema server side through the
`format` parameter, so the schema does NOT also need to go into the system
prompt. See docs/contracts.md for what works and what silently does not.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


# ======================================================================
# Shared enums
# ======================================================================

class Phase(str, Enum):
    bootstrap = "bootstrap"   # 0 - ~2M   : raise cash without infrastructure
    passive = "passive"       # ~2 - 20M  : first stations plus autotraders/miners
    scaling = "scaling"       # 20M+      : end-product stations, boarding


class ShipRole(str, Enum):
    miner = "miner"
    trader = "trader"
    combat = "combat"
    auxiliary = "auxiliary"   # scouts, resupply, drones, etc.


class TradeRule(str, Enum):
    own_faction_only = "own_faction_only"   # restrict all, own faction unticked
    open_market = "open_market"             # no restrictions


class Priority(str, Enum):
    critical = "critical"     # asset under attack / production frozen
    high = "high"
    normal = "normal"
    low = "low"


# ======================================================================
# SITREP  (executor -> model)
# ======================================================================

class StationState(BaseModel):
    id: str
    name: str
    sector: str
    manager_skill: Optional[int] = Field(
        None, ge=0, le=5, description="Manager stars 0-5; None = unknown"
    )
    produces: list[str] = Field(
        default_factory=list, description="Ware ids this station outputs"
    )
    starved_inputs: list[str] = Field(
        default_factory=list,
        description="Input wares that are missing or low and are holding back production",
    )
    container_fill: Optional[float] = Field(
        None, ge=0, le=1, description="Fraction full, end products; None = unknown"
    )
    solid_fill: Optional[float] = Field(
        None, ge=0, le=1, description="Fraction full, solid storage; None = unknown"
    )
    liquid_fill: Optional[float] = Field(
        None, ge=0, le=1, description="Fraction full, liquid storage; None = unknown"
    )
    assigned_miners: Optional[int] = None
    assigned_traders: Optional[int] = None
    idle_subordinates: Optional[int] = Field(
        None, description="Assigned ships reporting 'no buyer' or idle"
    )
    budget_fraction: Optional[float] = Field(
        None, ge=0, le=1, description="Operational budget relative to recommended"
    )
    net_profit_per_hour: Optional[float] = Field(
        None, description="Estimated recent credits/hour; negative means loss"
    )
    under_attack: bool = False


class FleetSummary(BaseModel):
    """Aggregated per role, no per-ship detail."""
    role: ShipRole
    total: int
    idle: int = Field(0, description="Ships without a task in this role")
    starved: int = Field(0, description="Ships finding no buyer or no resource")
    avg_pilot_skill: Optional[float] = Field(None, ge=0, le=5)
    example_ship_id: Optional[str] = Field(
        None, description="One id to aim actions at (e.g. a mimic leader)"
    )


class Threat(BaseModel):
    sector: str
    faction: str = Field(description="For example Xenon, Kha'ak, pirate")
    strength: Literal["minor", "moderate", "major"]
    threatened_assets: list[str] = Field(
        default_factory=list, description="Own station or fleet ids at risk"
    )


class Opportunity(BaseModel):
    """Pre-chewed by the executor; the model chooses, it does not compute."""
    kind: Literal["claim_ship", "trade_ware", "mining_sector", "mission", "boarding_target"]
    ref: str = Field(description="Target id or ware id")
    sector: str
    est_value: float = Field(description="Executor estimate: credits or credits/hour")
    in_range: bool = True
    note: Optional[str] = None


class Sitrep(BaseModel):
    tick: int = Field(description="Game time reference for ordering and memory")
    credits: float
    derived_phase: Phase = Field(description="Executor proposal; the planner may override")
    risk_budget: float = Field(
        ge=0, le=1, description="0 = conservative, 1 = aggressive; from user policy"
    )
    spend_cap_remaining: float = Field(
        description="Credits the planner may commit this cycle (guardrail)"
    )
    reputation: dict[str, float] = Field(
        default_factory=dict, description="faction -> reputation (-30..30)"
    )
    buildable_station_types: list[str] = Field(
        default_factory=list, description="Station types we hold blueprints for"
    )
    stations: list[StationState] = Field(default_factory=list)
    fleets: list[FleetSummary] = Field(default_factory=list)
    threats: list[Threat] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    active_goals: list[str] = Field(
        default_factory=list,
        description="Goals carried over from previous cycles (from the memory store)",
    )


# ======================================================================
# ACTIONS  (model -> executor)
# ======================================================================

# Note the field order in the action classes below: `type` comes FIRST.
# Pydantic puts inherited fields first, so with a base class providing
# `priority` and `rationale`, `type` ends up last in the JSON schema. Under
# grammar-constrained decoding the model then writes the rationale first and
# afterwards picks the cheapest branch of the union, which in practice was
# always `hold`. Measured 2026-08-19; see docs/contracts.md. Hence the
# deliberate repetition of `priority` and `rationale` instead of inheritance.
#
# Also note that `type` has no default. With a default, pydantic leaves it out
# of `required`, and the grammar then allows the model to skip the field
# entirely, after which validation fails on a missing discriminator.

_PRIORITY = Field(Priority.normal, description="Urgency of this action")
_RATIONALE = Field(description="One line: why. For logging and evaluation.")


class AssignShip(BaseModel):
    type: Literal["assign_ship"]
    ship_ref: str = Field(description="ship id or fleet id")
    station_id: str
    role: Literal["mine", "trade"]
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class SetBehaviour(BaseModel):
    type: Literal["set_behaviour"]
    ship_ref: str
    # "explore" maps to the vanilla Explore order and is the first behaviour the
    # bridge can actually execute; the others are still advice only.
    behaviour: Literal["autotrade", "automine", "repeat_orders", "explore"]
    whitelist: list[str] = Field(default_factory=list, description="Permitted wares")
    range_jumps: Optional[int] = Field(None, description="Leash range in jumps")
    anchor_sector: Optional[str] = None
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class SetTradeRule(BaseModel):
    type: Literal["set_trade_rule"]
    station_id: str
    ware: str
    rule: TradeRule
    side: Literal["buy", "sell", "both"]
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class SetPrice(BaseModel):
    type: Literal["set_price"]
    station_id: str
    ware: str
    mode: Literal["auto", "manual_max", "manual_offset"]
    offset_pct: Optional[float] = Field(
        None, description="E.g. -5 means 5% under average when mode=manual_offset"
    )
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class ClaimShip(BaseModel):
    type: Literal["claim_ship"]
    target_id: str
    retriever_pilot: bool = Field(
        True, description="First hire a cheap pilot to fetch the abandoned ship"
    )
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class Purchase(BaseModel):
    type: Literal["purchase"]
    item: Literal["ship", "module", "seminar", "blueprint"]
    spec: str = Field(description="What exactly, e.g. 'M miner' or 'management_seminar_3'")
    qty: int = 1
    max_spend: float = Field(description="Hard ceiling for this purchase")
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class BuildStation(BaseModel):
    type: Literal["build_station"]
    station_type: str
    sector: str
    modules: list[str] = Field(default_factory=list)
    max_spend: float = Field(description="Hard ceiling for this build")
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class FleetOrder(BaseModel):
    type: Literal["fleet_order"]
    fleet_id: str
    order: Literal["set_mimic_leader", "protect", "defend_sector", "retreat"]
    target: Optional[str] = Field(None, description="Leader id, protected asset, or sector")
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


class Hold(BaseModel):
    """Deliberately do nothing (consolidate, hold cash). Rationale required."""
    type: Literal["hold"]
    priority: Priority = _PRIORITY
    rationale: str = _RATIONALE


Action = Annotated[
    Union[
        AssignShip,
        SetBehaviour,
        SetTradeRule,
        SetPrice,
        ClaimShip,
        Purchase,
        BuildStation,
        FleetOrder,
        Hold,
    ],
    Field(discriminator="type"),
]


class PlannerResponse(BaseModel):
    assessment: str = Field(description="Two or three sentences reading the situation. Logged.")
    updated_goals: list[str] = Field(
        default_factory=list,
        description="Standing goals to persist for the next cycle",
    )
    actions: list[Action] = Field(
        default_factory=list, description="Ordered by priority, highest first"
    )
    watch: list[str] = Field(
        default_factory=list, description="Monitor, do not act on yet"
    )
    confidence: Literal["low", "medium", "high"] = "medium"
