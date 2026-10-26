"""Flight crew rosters (first 14 days): slots, qualifications, availability, double-booking."""
from datetime import timedelta

import polars as pl
import pytest

from helpers import BLOCKING, D, TS, TODAY, none, overlaps

ROSTER_END = TODAY + timedelta(days=13)


@pytest.fixture(scope="module")
def fa(T):
    f = T["flights"].select("flight_id", "aircraft_type", "crew_base_hub", "status", op=D("operating_date"), dep=TS("scheduled_dep_utc"), arr=TS("scheduled_arr_utc"),
                            blk=pl.col("block_minutes").cast(pl.Int64))
    t = T["aircraft_types"].select("aircraft_type", "family", "body_type", cab=pl.col("min_cabin_crew").cast(pl.Int64))
    return T["flight_crew_assignments"].join(f.join(t, on="aircraft_type"), on="flight_id")


def test_only_first_14_days_and_no_cancelled_flights(fa):
    none(fa.filter(pl.col("op") > ROSTER_END), "assignment beyond the roster window")
    none(fa.filter(pl.col("status") == "CANCELLED"), "assignment on a cancelled flight")


def test_assigned_has_employee_and_unfilled_has_none(T):
    a = T["flight_crew_assignments"]
    none(a.filter((pl.col("status") == "ASSIGNED") != pl.col("employee_id").is_not_null()), "ASSIGNED <-> employee_id")
    none(a.filter(~pl.col("status").is_in(["ASSIGNED", "UNFILLED"]) | ~pl.col("roster_status").is_in(["PUBLISHED", "DRAFT"])), "status enums")
    none(a.join(pl.DataFrame({"role": ["Pilot", "Pilot", "Cabin Crew", "Cabin Crew"], "slot": ["Captain", "First Officer", "Purser", "Cabin Attendant"]}), on=["role", "slot"], how="anti"), "role/slot pair")


def test_published_for_next_7_days_draft_after(T):
    j = T["flight_crew_assignments"].join(T["flights"].select("flight_id", op=D("operating_date")), on="flight_id")
    none(j.filter((pl.col("roster_status") == "PUBLISHED") != (pl.col("op") <= TODAY + timedelta(days=6))), "published window")


def test_every_rostered_flight_has_exactly_the_required_slots(T):
    f = T["flights"].filter((D("operating_date") <= ROSTER_END) & (pl.col("status") != "CANCELLED")).join(
        T["aircraft_types"].select("aircraft_type", cab=pl.col("min_cabin_crew").cast(pl.Int64)), on="aircraft_type")
    npil = pl.when(pl.col("block_minutes").cast(pl.Int64) < 480).then(2).when(pl.col("block_minutes").cast(pl.Int64) < 780).then(3).otherwise(4)
    exp = pl.concat([f.select("flight_id", slot=pl.lit("Captain"), want=pl.lit(1, dtype=pl.Int64)), f.select("flight_id", slot=pl.lit("First Officer"), want=(npil - 1).cast(pl.Int64)),
                     f.select("flight_id", slot=pl.lit("Purser"), want=pl.lit(1, dtype=pl.Int64)), f.select("flight_id", slot=pl.lit("Cabin Attendant"), want=(pl.col("cab") - 1).cast(pl.Int64))]).filter(pl.col("want") > 0)
    act = T["flight_crew_assignments"].group_by("flight_id", "slot").agg(have=pl.len())
    j = exp.join(act, on=["flight_id", "slot"], how="full", coalesce=True).with_columns(pl.col("want", "have").fill_null(0))
    none(j.filter(pl.col("want").cast(pl.Int64) != pl.col("have").cast(pl.Int64)), "slot count differs from requirement")


def test_assigned_crew_role_and_base(T, fa):
    a = fa.filter(pl.col("employee_id").is_not_null()).join(T["employees"].select("employee_id", "role", "sub_role", "home_hub"), on="employee_id", suffix="_e")
    none(a.filter((pl.col("role") != pl.col("role_e")) | (pl.col("slot") != pl.col("sub_role"))), "employee role/sub_role does not match slot")
    none(a.filter(pl.col("home_hub") != pl.col("crew_base_hub")), "crew not based at the flight's crew base")


def test_assigned_crew_hold_required_unexpired_skills(T, fa):
    a = fa.filter(pl.col("employee_id").is_not_null())
    need = pl.concat([
        a.filter(pl.col("role") == "Pilot").select("assignment_id", "employee_id", "op", skill=pl.lit("TR_") + pl.col("family")),
        a.filter(pl.col("role") == "Cabin Crew").select("assignment_id", "employee_id", "op", skill=pl.lit("CC_SEP")),
        a.filter(pl.col("role") == "Cabin Crew").select("assignment_id", "employee_id", "op", skill=pl.when(pl.col("body_type") == "wide").then(pl.lit("CQ_WIDE")).otherwise(pl.lit("CQ_NARROW"))),
    ])
    j = need.join(T["employee_skills"].select("employee_id", "skill_id", exp=D("expiry_date")), left_on=["employee_id", "skill"], right_on=["employee_id", "skill_id"], how="left")
    missing = need.join(T["employee_skills"].select("employee_id", "skill_id", exp=D("expiry_date")), left_on=["employee_id", "skill"], right_on=["employee_id", "skill_id"], how="anti")
    none(missing, "assigned without holding the required skill")
    none(j.filter(pl.col("exp") < pl.col("op")), "required skill expired before the flight date")


def test_assigned_crew_not_absent(T, fa):
    a = fa.filter(pl.col("employee_id").is_not_null()).with_columns(arr_d=pl.col("arr").dt.date())
    ev = T["availability_events"].filter(pl.col("status").is_in(BLOCKING)).select("employee_id", "event_id", "event_type", s=D("start_date"), e=D("end_date"))
    j = a.join(ev, on="employee_id")
    none(j.filter(((pl.col("op") >= pl.col("s")) & (pl.col("op") <= pl.col("e"))) | ((pl.col("arr_d") >= pl.col("s")) & (pl.col("arr_d") <= pl.col("e"))))
         .select("assignment_id", "employee_id", "event_id", "event_type"), "crew assigned while on leave / sick / training")


def test_no_crew_member_on_overlapping_flights(fa):
    none(overlaps(fa.filter(pl.col("employee_id").is_not_null()), "employee_id", "dep", "arr").select("employee_id", "flight_id", "dep", "_prev_end"), "crew double-booked")


def test_no_person_twice_on_one_flight(fa):
    none(fa.filter(pl.col("employee_id").is_not_null()).filter(pl.struct("flight_id", "employee_id").is_duplicated()).select("flight_id", "employee_id"), "duplicate person on flight")


def test_monthly_hours_cap_respected(T, fa):
    """The generator caps rostered block time at 115% of the 14-day share of monthly capacity."""
    hrs = fa.filter(pl.col("employee_id").is_not_null()).group_by("employee_id").agg(m=pl.col("blk").sum()).join(T["employees"].select("employee_id", cap=pl.col("monthly_capacity_hours").cast(pl.Float64)), on="employee_id")
    none(hrs.filter(pl.col("m") > pl.col("cap") * 60 * 14 / 30 * 1.15 + 1e-6), "rostered beyond hour cap")


def test_unfilled_share_is_small(T):
    a = T["flight_crew_assignments"]
    assert a.filter(pl.col("status") == "UNFILLED").height < 0.01 * a.height
