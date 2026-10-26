"""Employees, skills, contractors, availability events and training."""
import json
from datetime import timedelta

import polars as pl
import pytest

from helpers import BLOCKING, D, TODAY, none

ROLE_CAP = {"Pilot": 85, "Cabin Crew": 90, "Ground Staff": 150, "Maintenance Engineer": 140, "Operations Coordinator": 150}


def test_headcounts(T):
    e = T["employees"]; assert e.height == 45000
    rc = dict(e.group_by("role").len().iter_rows())
    assert rc["Maintenance Engineer"] == 7000 and rc["Operations Coordinator"] == 2400 and len(rc) == 5, rc
    assert sorted(e["employee_id"]) == [f"E{i:06d}" for i in range(1, 45001)]


def test_employee_fields(T):
    e = T["employees"].with_columns(fte_f=pl.col("fte").cast(pl.Float64), cap=pl.col("monthly_capacity_hours").cast(pl.Float64), cost=pl.col("hourly_cost_eur").cast(pl.Float64))
    none(e.filter((pl.col("contract_type") == "FULL_TIME") != (pl.col("fte_f") == 1.0) | ~pl.col("fte_f").is_between(0.5, 1.0)), "fte vs contract_type")
    base = pl.col("role").replace_strict(ROLE_CAP, return_dtype=pl.Float64)
    none(e.filter((pl.col("cap") - base * pl.col("fte_f")).abs() > 0.06), "capacity != role base * fte")
    none(e.filter(~pl.col("cost").is_between(10, 250)), "hourly cost out of range")
    none(e.filter(~D("hire_date").is_between(pl.date(1990, 1, 1), pl.lit(TODAY))), "hire_date")
    none(e.filter(pl.col("first_name").str.strip_chars() == "").vstack(e.filter(pl.col("last_name").str.strip_chars() == "")), "blank names")
    none(e.filter(~pl.col("current_status").is_in(["ACTIVE", "ON_LEAVE", "SICK", "IN_TRAINING"])), "current_status enum")
    pil = e.filter(pl.col("role") == "Pilot"); cab = e.filter(pl.col("role") == "Cabin Crew")
    none(pil.filter(~pl.col("sub_role").is_in(["Captain", "First Officer"]) | ~pl.col("primary_fleet").is_in(["A220", "E2", "A320FAM", "A330", "A350", "B787"])), "pilot sub_role/fleet")
    none(cab.filter(~pl.col("sub_role").is_in(["Purser", "Cabin Attendant"]) | ~pl.col("primary_fleet").is_in(["WIDE", "NARROW"])), "cabin sub_role/fleet")


def test_current_status_follows_todays_events(T):
    ev = T["availability_events"].filter(pl.col("status").is_in(["APPROVED", "ACTIVE", "ENROLLED"]) & (D("start_date") <= TODAY) & (D("end_date") >= TODAY))
    away = ev["employee_id"].unique()
    e = T["employees"].with_columns(away=pl.col("employee_id").is_in(away.implode()))
    none(e.filter((pl.col("current_status") != "ACTIVE") != pl.col("away")).select("employee_id", "current_status", "away"), "current_status vs events covering today")
    m = {"VACATION": "ON_LEAVE", "PARENTAL_LEAVE": "ON_LEAVE", "UNPAID_LEAVE": "ON_LEAVE", "SICK": "SICK", "TRAINING": "IN_TRAINING"}
    j = ev.join(e.select("employee_id", "current_status"), on="employee_id").with_columns(exp=pl.col("event_type").replace_strict(m))
    none(j.group_by("employee_id").agg(ok=(pl.col("exp") == pl.col("current_status")).any()).filter(~pl.col("ok")), "current_status is not one of today's event kinds")


# ------------------------------------------------------------------ skills
def test_skill_status_matches_expiry(T):
    s = T["employee_skills"].with_columns(x=D("expiry_date"))
    exp = pl.when(pl.col("x").is_null()).then(pl.lit("VALID")).when(pl.col("x") < TODAY).then(pl.lit("EXPIRED")).when(pl.col("x") <= TODAY + timedelta(days=60)).then(pl.lit("EXPIRING_SOON")).otherwise(pl.lit("VALID"))
    none(s.filter(pl.col("status") != exp), "status vs expiry_date as of 2026-10-26")


def test_expiry_only_for_skills_with_validity(T):
    j = T["employee_skills"].join(T["skills"].select("skill_id", "validity_months", "applicable_roles"), on="skill_id")
    none(j.filter(pl.col("expiry_date").is_not_null() != pl.col("validity_months").is_not_null()), "expiry_date <-> validity_months")
    none(j.filter(D("obtained_date") >= D("expiry_date")), "obtained_date on/after expiry_date")


def test_skills_not_obtained_in_the_future(T):
    none(T["employee_skills"].filter(D("obtained_date") > TODAY), "obtained_date in the future")


def test_employees_hold_only_applicable_skills(T):
    j = T["employee_skills"].join(T["skills"].select("skill_id", "applicable_roles"), on="skill_id").join(T["employees"].select("employee_id", "role"), on="employee_id")
    ok = (pl.col("applicable_roles") == "All") | pl.col("applicable_roles").str.split("|").list.contains(pl.col("role"))
    none(j.filter(~ok).group_by("role", "skill_id").len(), "skill held by a role it does not apply to")


def test_language_levels(T):
    s = T["employee_skills"]; lang = pl.col("skill_id").str.starts_with("LANG_")
    none(s.filter(lang & ~pl.col("level").is_in(["A1", "A2", "B1", "B2", "C1", "C2"])), "language without CEFR level")
    none(s.filter(~lang & pl.col("level").is_not_null()), "non-language with level")


def test_core_qualifications_present(T):
    held = T["employee_skills"].group_by("employee_id").agg(sk=pl.col("skill_id"))
    e = T["employees"].join(held, on="employee_id")
    has = lambda s: pl.col("sk").list.contains(s)
    none(e.filter(~has("SC_AIRPORT_ID")).select("employee_id"), "no airport ID")
    none(e.filter((pl.col("role") == "Pilot") & ~pl.col("sk").list.contains(pl.lit("TR_") + pl.col("primary_fleet"))).select("employee_id", "primary_fleet"), "pilot without type rating")
    none(e.filter((pl.col("role") == "Cabin Crew") & (~has("CC_SEP") | (~has("CQ_WIDE") & ~has("CQ_NARROW")))).select("employee_id"), "cabin crew without SEP/qualification")
    none(e.filter((pl.col("role") == "Maintenance Engineer") & ~(has("MC_B1") | has("MC_B2") | has("MC_C") | has("MC_TECH"))).select("employee_id"), "engineer without licence")


def test_contractors(T):
    c = T["contractors"]; assert c.height == 1900
    none(c.filter((D("contract_start") >= D("contract_end")) | (pl.col("day_rate_eur").cast(pl.Float64) <= 0) | pl.col("skills").is_null()), "contract window / rate / skills")


def test_contractors_json_matches_csv(T, root):
    js = json.loads((root / "json" / "contractors.json").read_text(encoding="utf-8"))
    assert [c["contractor_id"] for c in js] == T["contractors"]["contractor_id"].to_list()


# ------------------------------------------------------------------ availability
def test_availability_events_wellformed(T):
    a = T["availability_events"]
    none(a.filter((D("end_date") < D("start_date")) | (pl.col("days").cast(pl.Int64) != (D("end_date") - D("start_date")).dt.total_days() + 1)), "end/start/days")
    ok = pl.DataFrame({"event_type": ["VACATION", "VACATION", "SICK", "SICK", "PARENTAL_LEAVE", "UNPAID_LEAVE", "TRAINING"], "status": ["APPROVED", "PENDING", "RECORDED", "ACTIVE", "APPROVED", "APPROVED", "ENROLLED"]})
    none(a.join(ok, on=["event_type", "status"], how="anti"), "event_type/status combination")
    none(a.filter((pl.col("event_type") == "TRAINING") != pl.col("training_session_id").is_not_null()), "training_session_id only on TRAINING events")


# ------------------------------------------------------------------ training
def test_sessions(T):
    s = T["training_sessions"].with_columns(pl.col("capacity", "enrolled").cast(pl.Int64))
    none(s.filter((D("end_date") < D("start_date")) | (D("start_date") <= TODAY) | (pl.col("capacity") <= 0) | (pl.col("enrolled") > pl.col("capacity"))), "session dates/capacity")


def test_session_enrolled_counts_match_enrollments(T):
    n = T["training_enrollments"].group_by("session_id").len()
    j = T["training_sessions"].join(n, on="session_id", how="left").with_columns(pl.col("len").fill_null(0), enrolled=pl.col("enrolled").cast(pl.Int64))
    none(j.filter(pl.col("enrolled") != pl.col("len")).select("session_id", "enrolled", "len"), "enrolled != #enrollments")


def test_enrollments_have_matching_training_event(T):
    en, av, ss = T["training_enrollments"], T["availability_events"].filter(pl.col("event_type") == "TRAINING"), T["training_sessions"]
    assert av.height == en.height, "orphan TRAINING events or enrollments without event"
    j = en.join(av, left_on=["employee_id", "session_id"], right_on=["employee_id", "training_session_id"], how="left").join(ss.select("session_id", "start_date", "end_date"), on="session_id", suffix="_s")
    none(j.filter(pl.col("event_id").is_null() | (pl.col("start_date") != pl.col("start_date_s")) | (pl.col("end_date") != pl.col("end_date_s"))), "enrollment without matching event")
    none(en.filter(pl.struct("employee_id", "session_id").is_duplicated()), "duplicate enrollment")


def test_renewal_enrollments_are_for_held_skills(T):
    j = T["training_enrollments"].filter(pl.col("reason") == "RENEWAL_DUE").join(T["training_sessions"].select("session_id", "skill_id_granted"), on="session_id")
    none(j.filter(pl.col("skill_id_granted").is_null()), "renewal for a session granting nothing")
    none(j.join(T["employee_skills"].select("employee_id", "skill_id"), left_on=["employee_id", "skill_id_granted"], right_on=["employee_id", "skill_id"], how="anti"), "renewal for a skill the employee does not hold")


def test_training_does_not_clash_with_other_absences(T):
    a = T["availability_events"].filter(pl.col("status").is_in(BLOCKING)).select("employee_id", "event_id", "event_type", s=D("start_date"), e=D("end_date"))
    t = a.filter(pl.col("event_type") == "TRAINING")
    j = t.join(a.filter(pl.col("event_type") != "TRAINING"), on="employee_id", suffix="_o")
    none(j.filter((pl.col("s_o") <= pl.col("e")) & (pl.col("e_o") >= pl.col("s"))).select("employee_id", "event_id", "event_id_o", "event_type_o"), "training overlaps another absence")


def test_open_course_codes_have_no_enrolments(T):
    """README: TR_CONV, MX_TYPE and PURSER sessions have no enrolments yet."""
    s = T["training_sessions"].filter(pl.col("course_code").is_in(["TR_CONV", "MX_TYPE", "PURSER"]))
    none(s.join(T["training_enrollments"], on="session_id"), "enrolments on open-capacity courses")
