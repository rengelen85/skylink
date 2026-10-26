"""Concrete flights: consistency with the schedule, aircraft usage, gates, statuses."""
from datetime import date, datetime, timedelta

import polars as pl
import pytest

from helpers import D, NOW, TS, TODAY, none, overlaps


@pytest.fixture(scope="module")
def fl(T):
    return T["flights"].with_columns(op=D("operating_date"), dep=TS("scheduled_dep_utc"), arr=TS("scheduled_arr_utc"),
                                     blk=pl.col("block_minutes").cast(pl.Int64), seats_i=pl.col("seats").cast(pl.Int64),
                                     pax=pl.col("booked_pax").cast(pl.Int64), lf=pl.col("load_factor").cast(pl.Float64))


def test_window_is_28_days_from_today(fl):
    assert sorted(fl["op"].unique().to_list()) == [TODAY + timedelta(days=k) for k in range(28)]


def test_flight_id_format(fl):
    none(fl.filter(pl.col("flight_id") != pl.col("flight_number") + "_" + pl.col("operating_date").str.replace_all("-", "")), "flight_id")


def test_flight_count_equals_schedule_expanded(T, fl):
    days = [TODAY + timedelta(days=k) for k in range(28)]
    exp = sum(sum(str(d.isoweekday()) in m for d in days) for m in T["flight_schedule"]["days_of_week"])
    assert fl.height == exp


def test_flights_match_their_schedule_pattern(T, fl):
    s = T["flight_schedule"].select("flight_number", "days_of_week", "scheduled_dep_time_utc", doff=pl.col("dep_day_offset").cast(pl.Int64),
                                    o="origin", d="destination", t="aircraft_type", b="block_minutes", km="distance_km", c="crew_base_hub", p="rotation_pair_id")
    j = fl.join(s, on="flight_number")
    assert j.height == fl.height
    exp_dep = pl.col("op").cast(pl.Datetime("us")) + pl.duration(days=pl.col("doff"), hours=pl.col("scheduled_dep_time_utc").str.slice(0, 2).cast(pl.Int64),
                                                                  minutes=pl.col("scheduled_dep_time_utc").str.slice(3, 2).cast(pl.Int64))
    none(j.filter(~pl.struct("days_of_week", "op").map_elements(lambda r: str(r["op"].isoweekday()) in r["days_of_week"], return_dtype=pl.Boolean)), "runs on a day outside its pattern")
    none(j.filter(pl.col("dep") != exp_dep), "departure time differs from schedule")
    none(j.filter(pl.col("arr") - pl.col("dep") != pl.duration(minutes=pl.col("blk"))), "arrival != departure + block")
    none(j.filter((pl.col("origin") != pl.col("o")) | (pl.col("destination") != pl.col("d")) | (pl.col("aircraft_type") != pl.col("t")) | (pl.col("block_minutes") != pl.col("b"))
                  | (pl.col("distance_km") != pl.col("km")) | (pl.col("crew_base_hub") != pl.col("c")) | (pl.col("rotation_pair_id") != pl.col("p"))), "attributes differ from schedule")


def test_seats_pax_and_load_factor(T, fl):
    t = T["aircraft_types"].select("aircraft_type", ts=pl.col("seats").cast(pl.Int64))
    j = fl.join(t, on="aircraft_type")
    none(j.filter((pl.col("seats_i") != pl.col("ts")) | (pl.col("pax") < 0) | (pl.col("pax") > pl.col("seats_i"))
                  | ((pl.col("pax") / pl.col("seats_i") - pl.col("lf")).abs() > 0.01) | ~pl.col("lf").is_between(0.45, 0.99)), "seats / pax / load factor")


def test_status_follows_reference_time(fl):
    exp = pl.when(pl.col("dep") >= NOW).then(pl.lit("SCHEDULED")).when(pl.col("arr") < NOW).then(pl.lit("COMPLETED")).otherwise(pl.lit("AIRBORNE"))
    none(fl.filter(~pl.col("status").is_in(["SCHEDULED", "AIRBORNE", "COMPLETED", "CANCELLED"])), "status enum")
    none(fl.filter((pl.col("status") != "CANCELLED") & (pl.col("status") != exp)), "status vs 08:26Z on 2026-10-26")
    none(fl.filter((pl.col("status") == "CANCELLED") & (pl.col("arr") < NOW)), "an already-landed flight is cancelled")


def test_tail_matches_type_and_nearly_always_assigned(T, fl):
    j = fl.filter(pl.col("aircraft_tail").is_not_null()).join(T["aircraft"].select("tail_number", t2="aircraft_type"), left_on="aircraft_tail", right_on="tail_number")
    none(j.filter(pl.col("aircraft_type") != pl.col("t2")), "tail is a different aircraft type")
    assert fl["aircraft_tail"].null_count() < 0.01 * fl.height, f"{fl['aircraft_tail'].null_count()} flights have no tail"


def test_no_aircraft_flies_two_flights_at_once(fl):
    none(overlaps(fl.filter(pl.col("aircraft_tail").is_not_null()), "aircraft_tail", "dep", "arr").select("aircraft_tail", "flight_id", "dep", "_prev_end"), "tail double-booked")


def test_no_flight_uses_aircraft_in_open_maintenance(T, fl):
    m = T["maintenance_activities"].filter(pl.col("status") != "COMPLETED").select("tail_number", "activity_id", s=TS("planned_start_utc"), e=TS("planned_end_utc"))
    j = fl.filter((pl.col("status") != "COMPLETED") & pl.col("aircraft_tail").is_not_null()).join(m, left_on="aircraft_tail", right_on="tail_number")
    none(j.filter((pl.col("s") < pl.col("arr")) & (pl.col("e") > pl.col("dep"))).select("flight_id", "aircraft_tail", "activity_id"), "flight during maintenance")


def test_tail_positioning_breaks_are_rare(T, fl):
    """README admits ~377 tails start from the wrong airport; guard against it growing."""
    a = T["aircraft"].select("tail_number", "home_hub")
    f = fl.filter(pl.col("aircraft_tail").is_not_null()).sort("aircraft_tail", "dep").join(a, left_on="aircraft_tail", right_on="tail_number")
    f = f.with_columns(prev=pl.col("destination").shift(1).over("aircraft_tail").fill_null(pl.col("home_hub")))
    breaks = f.filter(pl.col("origin") != pl.col("prev")).height
    assert breaks < 0.02 * fl.height, f"{breaks} non-contiguous tail positions"


def test_gates(T, fl):
    g = T["airport_gates"].select("gate_id", "airport", "max_body_type")
    t = T["aircraft_types"].select("aircraft_type", "body_type")
    j = fl.filter(pl.col("dep_gate_id").is_not_null()).join(g, left_on="dep_gate_id", right_on="gate_id").join(t, on="aircraft_type")
    none(j.filter(pl.col("airport") != pl.col("origin")), "gate not at origin")
    none(j.filter((pl.col("body_type") == "wide") & (pl.col("max_body_type") != "WIDE")), "wide-body at narrow-only gate")
    gaps = j.sort("dep_gate_id", "dep").with_columns(gap=(pl.col("dep") - pl.col("dep").shift(1).over("dep_gate_id")))
    none(gaps.filter(pl.col("gap") < timedelta(minutes=60)).select("dep_gate_id", "flight_id", "gap"), "gate reused < 60 min apart")
    hub = fl.filter(pl.col("origin").is_in(T["airports"].filter(pl.col("is_hub") == "1")["airport_iata"].implode()))
    assert hub["dep_gate_id"].null_count() < 0.05 * hub.height
