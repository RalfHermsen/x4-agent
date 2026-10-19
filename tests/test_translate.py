"""After 2.4: the parser in front of call 2 (step 1), prices are Python's (step 2)."""

import action_lines
import planner
from schemas import PlannerResponse

REPORT = """# OWN STATIONS
KYV-745 (station_gen_factory_base_01_macro) in Hewa's Twin I

# FLEET (2 ships)
ASO-629 container freighter (ship_m), working for itself: IDLE, docked at KYV-745
PQA-833 scout (ship_s), working for itself: IDLE, in Hewa's Twin I
"""


def _fake_extract(calls):
    def extract(analysis, report, model):
        calls.append(analysis)
        return PlannerResponse.model_validate({
            "assessment": "call 2", "updated_goals": ["from call 2"],
            "actions": [{"type": "set_behaviour", "ship_ref": "PQA-833",
                         "behaviour": "explore", "rationale": "call 2"}]}), 1.5
    return extract


def test_every_line_read_means_no_model_call(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    analysis = ("Storage is full at KYV-745.\n\nACTIONS:\n"
                "1. ASO-629: Assign to KYV-745 as a trader\n\n"
                "STANDING GOALS:\n- Clear the storage at KYV-745\n")
    plan, seconds = planner.translate(analysis, REPORT, "any")
    assert calls == [] and seconds == 0.0
    assert [(a.type, a.ship_ref, a.station_id, a.role) for a in plan.actions] == [
        ("assign_ship", "ASO-629", "KYV-745", "trade")]
    assert plan.actions[0].rationale.startswith("read from the reasoning: 1. ASO-629")
    assert plan.updated_goals == ["Clear the storage at KYV-745"]
    assert plan.assessment == "Storage is full at KYV-745."


def test_only_the_unread_lines_go_to_call_2(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    analysis = ("ACTIONS:\n1. ASO-629: Assign to KYV-745 as a trader\n"
                "2. PQA-833: scout the sectors around Hewa's Twin for buyers\n\n"
                "STANDING GOALS:\n- Grow\n")
    plan, seconds = planner.translate(analysis, REPORT, "any")
    assert len(calls) == 1
    assert "2. PQA-833" in calls[0] and "ASO-629" not in calls[0]
    assert "STANDING GOALS" in calls[0]
    assert [a.type for a in plan.actions] == ["assign_ship", "set_behaviour"]
    assert plan.updated_goals == ["Grow"] and seconds == 1.5


def test_goals_come_from_call_2_when_the_reasoning_has_none(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    plan, _ = planner.translate("ACTIONS:\n1. PQA-833: look around\n", REPORT, "any")
    assert plan.updated_goals == ["from call 2"]


def test_without_a_heading_call_2_reads_everything(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    analysis = "Assign ASO-629 to KYV-745 as a trader."
    planner.translate(analysis, REPORT, "any")
    assert calls == [analysis]


def test_unnumbered_actions_still_reach_call_2(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    analysis = "ACTIONS:\n- ASO-629: Assign to KYV-745 as a trader\n"
    planner.translate(analysis, REPORT, "any")
    assert calls == [analysis]


def test_actions_none_needs_no_model(monkeypatch):
    calls = []
    monkeypatch.setattr(planner, "extract", _fake_extract(calls))
    plan, seconds = planner.translate(
        "All is well.\n\nACTIONS: none\n\nSTANDING GOALS:\n- Keep going\n", REPORT, "any")
    assert calls == [] and seconds == 0.0
    assert plan.actions == [] and plan.updated_goals == ["Keep going"]


def test_goals_and_summary_are_plain_lines():
    analysis = ("**THINKING**\nThe fleet is idle.\n\nMore.\n\n**ACTIONS**\n1. x\n\n"
                "**STANDING GOALS**\n- First goal\n2. Second goal\n* Third goal\n- Fourth\n")
    assert action_lines.goals_from(analysis) == ["First goal", "Second goal", "Third goal"]
    assert action_lines.summary_from("The fleet is idle.\n\nMore.\n\nACTIONS:\n1. x") == \
        "The fleet is idle."
    assert action_lines.says_none("ACTIONS: none") and not action_lines.says_none("ACTIONS:\n1. x")


def test_a_proposed_price_is_refused_with_the_reason(small_state):
    plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "set_price", "station_id": "KYV-745", "ware": "energycells", "side": "sell",
         "price": 21, "rationale": "model"}]})
    ok, rejected = planner.check_actions(plan, small_state)
    assert ok == []
    assert rejected[0][1] == planner.PRICE_REFUSAL


def test_a_station_where_the_ship_goes_is_refused(small_state):
    plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "assign_ship", "ship_ref": "KYV-745", "station_id": "KYV-745",
         "role": "trade", "rationale": "Assign a trader to sell refined metals"}]})
    ok, rejected = planner.check_actions(plan, small_state)
    assert ok == [] and "is not a ship" in rejected[0][1]


def test_the_action_cap_is_a_setting():
    assert "at\nmost four concrete actions" in planner.reason_system(4)
    assert "at\nmost eight concrete actions" in planner.reason_system(8)
    assert "{max_actions}" not in planner.reason_system()
