"""Disruptions, forecasting, budgets, new routes, hubs_nested.json and the stories the README promises."""
import json
from datetime import timedelta

import polars as pl
import pytest

from helpers import D, NOW, TS, TODAY, none


# ------------------------------------------------------------------ disruptions
def test_disruption_times_status_severity(T):
    d = T["disruptions"].with_columns(s=TS("start_utc"), e=TS("end_utc"))
    exp = pl.when(pl.col("e") < NOW).then(pl.lit("RESOLVED")).when(pl.col("s") <= NOW).then(pl.lit("ACTIVE")).otherwise(pl.lit("FORECAST"))
    none(d.filter((pl.col("e") <= pl.col("s")) | (pl.col("status") != exp)), "time order / status vs now")
    none(d.filter(~pl.col("severity").is_in(["LOW", "MEDIUM", "HIGH", "SEVERE"]) | ~pl.col("airport_capacity_reduction_pct").cast(pl.Int64).is_between(1, 100)), "severity / capacity %")


def test_planted_disruptions(T):
    d = T["disruptions"]
    assert dict(d.group_by("status").len().iter_rows()) == {"ACTIVE": 1, "FORECAST": 8, "RESOLVED": 10}  # Storm x3, ATC, snow x2, FCO strike, MUC outage
    pairs = set(zip(d["event_group"], d["hub"]))
    assert {("Fog ZRH 26-Oct", "ZRH"), ("Storm Aurelia", "AMS"), ("Storm Aurelia", "FRA"), ("Storm Aurelia", "CPH"), ("French ATC action", "CDG"),
            ("Early snow Nordics", "ARN"), ("Italian ground handling strike", "FCO")} <= pairs


def test_impacts(T):
    i = T["disruption_flight_impacts"].join(T["disruptions"].select("disruption_id", "hub", "severity"), on="disruption_id").join(
        T["flights"].select("flight_id", "origin", "destination"), on="flight_id")
    none(i.filter((pl.col("hub") != pl.col("origin")) & (pl.col("hub") != pl.col("destination"))), "disruption hub not on the flight's route")
    none(i.filter(~pl.col("risk_score").cast(pl.Float64).is_between(0, 0.99, closed="right")), "risk score")
    none(i.filter(pl.col("impact_type") != pl.when(pl.col("severity").is_in(["HIGH", "SEVERE"])).then(pl.lit("CANCELLATION_RISK")).otherwise(pl.lit("DELAY_RISK"))), "impact type vs severity")


# ------------------------------------------------------------------ forecasting / budgets
def test_network_plan(T):
    n = T["network_plan_monthly"]
    assert n.height == 210 and n["hub"].n_unique() == 15 and n["month"].n_unique() == 14 and n["month"].min() == "2026-11" and n["month"].max() == "2027-12"
    none(n.filter(~(pl.col("forecast_passengers_low").cast(pl.Int64) <= pl.col("forecast_passengers_base").cast(pl.Int64)) | ~(pl.col("forecast_passengers_base").cast(pl.Int64) <= pl.col("forecast_passengers_high").cast(pl.Int64))
                  | ~pl.col("expected_load_factor").cast(pl.Float64).is_between(0, 1, closed="right")), "low <= base <= high / load factor")


def test_history(T):
    h = T["monthly_operations_history"].with_columns(pl.col("demand_hours", "available_hours").cast(pl.Float64), u=pl.col("utilization_pct").cast(pl.Float64))
    none(h.filter((100 * pl.col("demand_hours") / pl.col("available_hours") - pl.col("u")).abs() > 0.2), "utilization != demand/available")
    none(h.filter(~pl.col("sickness_rate_pct").cast(pl.Float64).is_between(0, 30)), "sickness")
    months = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if f"{y}-{m:02d}" <= "2026-09"]
    g = h.group_by("hub", "role").agg(m=pl.col("month").sort())
    none(g.filter(pl.col("m").list.len() != len(months)), "gap in months")
    assert g["m"][0].to_list() == months


def test_history_delay_percentage_is_a_percentage(T):
    none(T["monthly_operations_history"].filter(~pl.col("delayed_flights_pct").cast(pl.Float64).is_between(0, 100)).select("month", "hub", "role", "delayed_flights_pct"), "delayed_flights_pct > 100")


def test_budgets(T):
    b = T["budgets"]
    assert set(b["month"]) == {f"{y}-{m:02d}" for y in (2026, 2027) for m in range(1, 13)}
    none(b.filter(pl.col("actual_labor_cost_eur").is_not_null() != (pl.col("month") <= "2026-09")), "actuals present exactly for past months")
    none(b.filter((pl.col("budget_headcount").cast(pl.Int64) <= 0) | (pl.col("budget_labor_cost_eur").cast(pl.Int64) <= 0)), "non-positive budget")


# ------------------------------------------------------------------ routes, events, rules
def test_new_routes(T):
    n = T["new_route_launches"]; assert n.height == 8
    none(n.filter((D("launch_date") <= TODAY) | ~pl.col("frequency_per_week").cast(pl.Int64).is_between(1, 7) | (pl.col("origin") == pl.col("destination"))), "route launch fields")
    r = T["new_route_requirements"].join(n.select("route_launch_id", "launch_date"), on="route_launch_id")
    none(r.filter((D("ready_by_date") >= D("launch_date")) | (pl.col("headcount_required").cast(pl.Int64) <= 0)), "ready-by after launch / headcount")
    assert T["candidate_hubs"].height == 3


def test_events_rules_service_requirements(T):
    none(T["special_events"].filter((D("end_date") < D("start_date")) | (pl.col("expected_additional_passengers").cast(pl.Int64) <= 0)), "special events")
    s = T["service_requirements"]
    none(s.filter((pl.col("headcount").cast(pl.Int64) <= 0) | ((pl.col("duration_basis") != "block_time") & pl.col("fixed_hours").is_null())), "service requirements")
    none(T["regulatory_rules"].filter(pl.col("limit_value").cast(pl.Float64) <= 0), "rule limit")


def test_hubs_nested_json_matches_tables(T, root):
    hn = json.loads((root / "json" / "hubs_nested.json").read_text(encoding="utf-8"))
    hubs = set(T["airports"].filter(pl.col("is_hub") == "1")["airport_iata"])
    assert {h["hub"] for h in hn} == hubs and len(hn) == 15
    hc = {(h, r): n for h, r, n in T["employees"].group_by("home_hub", "role").len().iter_rows()}
    gc = dict(T["airport_gates"].group_by("airport").len().iter_rows())
    ac = {(h, f): n for h, f, n in T["aircraft"].group_by("home_hub", "family").len().iter_rows()}
    fc = dict(T["maintenance_facilities"].group_by("hub").len().iter_rows())
    for h in hn:
        assert h["gates"] == gc[h["hub"]], h["hub"]
        assert h["headcount"] == {r: hc.get((h["hub"], r), 0) for r in h["headcount"]}, h["hub"]
        assert h["aircraft_homed"] == {f: ac.get((h["hub"], f), 0) for f in h["aircraft_homed"]}, h["hub"]
        assert len(h["facilities"]) == fc[h["hub"]], h["hub"]


# ------------------------------------------------------------------ README stories
def _util(T, hub, role):
    h = T["monthly_operations_history"].filter((pl.col("month") == "2026-09") & (pl.col("hub") == hub) & (pl.col("role") == role))
    return float(h["utilization_pct"][0])


def test_story_understaffed_and_spare_capacity(T):
    assert _util(T, "FCO", "Cabin Crew") >= 95
    assert _util(T, "ATH", "Ground Staff") > 120
    assert 88 <= _util(T, "BCN", "Pilot") <= 98
    assert 92 <= _util(T, "CDG", "Operations Coordinator") <= 102
    assert _util(T, "WAW", "Pilot") <= 72
    assert _util(T, "ARN", "Ground Staff") <= 66


def test_story_aircraft(T):
    a, m = T["aircraft"], T["maintenance_activities"]
    assert a.filter(pl.col("status") == "AOG").height == 12
    assert 15 <= a.filter(pl.col("status") == "IN_MAINTENANCE").height <= 30
    assert m.filter((pl.col("activity_type") == "DEFERRED_DEFECT") & (pl.col("status") == "PLANNED")).height == 100


def test_story_compliance(T):
    c = dict(T["employee_skills"].group_by("status").len().iter_rows())
    assert 2250 <= c["EXPIRED"] <= 3750 and 8600 <= c["EXPIRING_SOON"] <= 14400, c


def test_story_summer_peak(T):
    pend = (T["availability_events"].filter(pl.col("status") == "PENDING").with_columns(m=D("start_date").dt.strftime("%Y-%m")).group_by("m").len().sort("len", descending=True))
    assert set(pend["m"][:2]) == {"2027-07", "2027-08"}, pend.head(3)
    n = T["network_plan_monthly"].with_columns(pl.col("planned_flights").cast(pl.Int64)).group_by("month").agg(f=pl.col("planned_flights").sum())
    f = dict(n.iter_rows())
    summer = (f["2027-07"] + f["2027-08"]) / 2; winter = sum(f[m] for m in ("2026-11", "2026-12", "2027-01", "2027-02")) / 4
    # README: ~22% above the annual baseline = seasonal index 1.22; planned flights are ~45% above Nov-Feb. Guard both loosely.
    assert summer / winter >= 1.15, summer / winter
    si = T["network_plan_monthly"].filter(pl.col("month").is_in(["2027-07", "2027-08"]))["seasonal_index"].cast(pl.Float64)
    assert 1.15 <= si.mean() <= 1.30, si.mean()
