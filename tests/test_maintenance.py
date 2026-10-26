"""Aircraft, maintenance activities, requirements and engineer assignments."""
from datetime import timedelta

import polars as pl
import pytest

from helpers import BLOCKING, D, NOW, TODAY, TS, none, overlaps


@pytest.fixture(scope="module")
def act(T):
    return T["maintenance_activities"].with_columns(s=TS("planned_start_utc"), e=TS("planned_end_utc"), mh=pl.col("estimated_man_hours").cast(pl.Int64))


def test_650_aircraft_and_fleet_split(T):
    a = T["aircraft"]; assert a.height == 650
    cnt = a.group_by("aircraft_type").len().join(T["aircraft_types"].select("aircraft_type", fs=pl.col("fleet_size").cast(pl.UInt32)), on="aircraft_type")
    none(cnt.filter(pl.col("len") != pl.col("fs")), "fleet size per type")


def test_aircraft_attributes(T):
    j = T["aircraft"].join(T["aircraft_types"].select("aircraft_type", f="family", s="seats"), on="aircraft_type")
    none(j.filter((pl.col("family") != pl.col("f")) | (pl.col("seats") != pl.col("s"))), "family/seats differ from type")
    none(j.filter(~pl.col("status").is_in(["ACTIVE", "IN_MAINTENANCE", "AOG"]) | (pl.col("total_flight_hours").cast(pl.Int64) < 0) | (pl.col("total_cycles").cast(pl.Int64) < 0)), "status/hours")
    none(j.filter(D("delivery_date") > TODAY), "delivered in the future")
    for n in "ac":
        none(j.filter(pl.col(f"last_{n}_check_date").is_not_null() & pl.col(f"next_{n}_check_due").is_not_null() & (D(f"last_{n}_check_date") >= D(f"next_{n}_check_due"))), f"{n}-check last >= next")
        none(j.filter(D(f"last_{n}_check_date") > TODAY), f"{n}-check last in future")
        # a check that is running right now is still "next" and started in the past; only idle aircraft must have a future date
        none(j.filter((D(f"next_{n}_check_due") < TODAY) & (pl.col("status") == "ACTIVE")), f"{n}-check next due in the past")


def test_activity_time_and_status(act):
    none(act.filter(pl.col("e") <= pl.col("s")), "end <= start")
    exp = pl.when(pl.col("e") < NOW).then(pl.lit("COMPLETED")).when(pl.col("s") <= NOW).then(pl.lit("IN_PROGRESS")).otherwise(pl.lit("PLANNED"))
    none(act.filter(pl.col("status") != exp), "status vs 08:26Z on 2026-10-26")


def test_activity_enums_and_aog_flag(act):
    none(act.filter(~pl.col("activity_type").is_in(["A_CHECK", "C_CHECK", "UNSCHEDULED_DEFECT", "DEFERRED_DEFECT"]) | ~pl.col("priority").is_in(["ROUTINE", "HIGH", "AOG"])), "enums")
    none(act.filter((pl.col("aog_flag") == "1") != (pl.col("priority") == "AOG")), "aog_flag <-> AOG priority")
    none(act.filter(pl.col("mh") <= 0), "man hours")


def test_facility_matches_activity(T, act):
    j = act.join(T["maintenance_facilities"].select("facility_id", "facility_type", "supported_families", fh="hub"), on="facility_id").join(T["aircraft"].select("tail_number", "family"), on="tail_number")
    none(j.filter(pl.col("hub") != pl.col("fh")), "activity hub != facility hub")
    none(j.filter((pl.col("activity_type") == "C_CHECK") != (pl.col("facility_type") == "BASE_MAINTENANCE")), "C-checks belong in base hangars only")
    none(j.filter(~pl.struct("supported_families", "family").map_elements(lambda r: r["family"] in r["supported_families"].split("|"), return_dtype=pl.Boolean)), "facility does not support family")


def test_aircraft_status_follows_in_progress_work(T, act):
    ip = act.filter(pl.col("status") == "IN_PROGRESS").group_by("tail_number").agg(aog=(pl.col("aog_flag") == "1").any(), chk=pl.col("activity_type").is_in(["A_CHECK", "C_CHECK"]).any())
    j = T["aircraft"].join(ip, on="tail_number", how="left").with_columns(pl.col("aog", "chk").fill_null(False))
    exp = pl.when(pl.col("aog")).then(pl.lit("AOG")).when(pl.col("chk")).then(pl.lit("IN_MAINTENANCE")).otherwise(pl.lit("ACTIVE"))
    none(j.filter(pl.col("status") != exp).select("tail_number", "status", "aog", "chk"), "aircraft.status vs in-progress maintenance")


def test_base_hangar_never_over_capacity(T, act):
    c = act.filter(pl.col("activity_type") == "C_CHECK").select("facility_id", day=pl.date_ranges(pl.col("s").dt.date(), pl.col("e").dt.date() - timedelta(days=1))).explode("day")
    occ = c.group_by("facility_id", "day").len().join(T["maintenance_facilities"].select("facility_id", bays=pl.col("hangar_bays").cast(pl.UInt32)), on="facility_id")
    none(occ.filter(pl.col("len") > pl.col("bays")), "more C-checks than bays on a day")


def test_no_overlapping_checks_per_aircraft(act):
    c = act.filter(pl.col("activity_type").is_in(["A_CHECK", "C_CHECK"])).with_columns(k=pl.col("tail_number") + pl.col("activity_type"))
    none(overlaps(c, "k", "s", "e").select("k", "activity_id", "s", "_prev_end"), "overlapping checks")


def test_requirements(T, act):
    r = T["maintenance_requirements"].join(act.select("activity_id", "status", "tail_number"), on="activity_id").join(T["aircraft"].select("tail_number", "family"), on="tail_number")
    none(r.filter(pl.col("status") == "COMPLETED"), "requirement on a completed activity")
    none(r.filter((pl.col("required_type_skill").is_null()) != (pl.col("sub_role") == "Technician")), "type skill null iff Technician")
    none(r.filter(pl.col("required_type_skill").is_not_null() & (pl.col("required_type_skill") != pl.lit("MT_") + pl.col("family"))), "type endorsement for another family")
    none(r.filter((pl.col("headcount").cast(pl.Int64) <= 0) | (pl.col("hours_each").cast(pl.Float64) <= 0)), "non-positive headcount/hours")
    lic = {"B1 Engineer": "MC_B1", "B2 Engineer": "MC_B2", "Base Maintenance Certifier": "MC_C", "Technician": "MC_TECH"}
    none(r.filter(pl.col("required_license_skill") != pl.col("sub_role").replace(lic)), "licence does not match sub_role")


def test_assignments(T, act):
    a = T["maintenance_assignments"]
    q = T["maintenance_requirements"].select("requirement_id", "activity_id", "required_license_skill", "required_type_skill", hc=pl.col("headcount").cast(pl.UInt32))
    j = a.join(q, on="requirement_id", suffix="_q")
    none(j.filter(pl.col("activity_id") != pl.col("activity_id_q")), "requirement belongs to another activity")
    none(a.filter((pl.col("status") == "ASSIGNED") != pl.col("employee_id").is_not_null()), "ASSIGNED <-> employee_id")
    none(a.group_by("requirement_id").len().join(q, on="requirement_id").filter(pl.col("len") > pl.col("hc")), "more rows than headcount")
    none(a.filter(pl.col("employee_id").is_not_null()).filter(pl.struct("activity_id", "employee_id").is_duplicated()), "engineer twice on one activity")
    none(a.join(act.select("activity_id", "s"), on="activity_id").filter(pl.col("s") > NOW + timedelta(days=28)), "assignment for an activity beyond 28 days")


def test_assigned_engineers_are_local_qualified_and_available(T, act):
    a = T["maintenance_assignments"].filter(pl.col("status") == "ASSIGNED").join(
        T["maintenance_requirements"].select("requirement_id", "required_license_skill", "required_type_skill"), on="requirement_id").join(
        act.select("activity_id", "hub", sd=pl.col("s").dt.date()), on="activity_id").join(T["employees"].select("employee_id", "role", "home_hub"), on="employee_id")
    none(a.filter(pl.col("role") != "Maintenance Engineer"), "assigned person is not an engineer")
    none(a.filter(pl.col("home_hub") != pl.col("hub")), "engineer based at another hub")
    need = pl.concat([a.select("assignment_id", "employee_id", "sd", skill="required_license_skill"), a.filter(pl.col("required_type_skill").is_not_null()).select("assignment_id", "employee_id", "sd", skill="required_type_skill")])
    sk = T["employee_skills"].select("employee_id", "skill_id", exp=D("expiry_date"))
    none(need.join(sk, left_on=["employee_id", "skill"], right_on=["employee_id", "skill_id"], how="anti"), "engineer lacks required skill")
    none(need.join(sk, left_on=["employee_id", "skill"], right_on=["employee_id", "skill_id"]).filter(pl.col("exp") < pl.col("sd")), "required skill expired before activity")
    ev = T["availability_events"].filter(pl.col("status").is_in(BLOCKING)).select("employee_id", "event_id", s=D("start_date"), e=D("end_date"))
    none(a.join(ev, on="employee_id").filter((pl.col("sd") >= pl.col("s")) & (pl.col("sd") <= pl.col("e"))).select("assignment_id", "employee_id", "event_id"), "engineer absent on activity start")
