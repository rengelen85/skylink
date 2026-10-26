"""Files, row counts, CSV/JSON parity, primary keys and foreign keys."""
import json

import polars as pl
import pytest

from helpers import none

JSON_MAX_ROWS = 60000

PK = dict(airports=["airport_iata"], aircraft_types=["aircraft_type"], aircraft=["tail_number"], employees=["employee_id"], contractors=["contractor_id"],
          maintenance_facilities=["facility_id"], airport_gates=["gate_id"], skills=["skill_id"], employee_skills=["employee_id", "skill_id"],
          flight_schedule=["flight_number"], flights=["flight_id"], maintenance_activities=["activity_id"], maintenance_requirements=["requirement_id"],
          training_sessions=["session_id"], new_route_launches=["route_launch_id"], special_events=["event_id"], service_requirements=["requirement_id"],
          flight_crew_assignments=["assignment_id"], maintenance_assignments=["assignment_id"], availability_events=["event_id"],
          training_enrollments=["enrollment_id"], disruptions=["disruption_id"], disruption_flight_impacts=["disruption_id", "flight_id"],
          calendar=["date"], network_plan_monthly=["month", "hub"], monthly_operations_history=["month", "hub", "role"], budgets=["month", "hub", "role"],
          regulatory_rules=["rule_id"], candidate_hubs=["candidate_id"], new_route_requirements=["route_launch_id", "role", "sub_role"])

# (child table, column, parent table, parent column, nullable, list separator)
FK = [
    ("employees", "home_hub", "hubs", None, 0, None), ("employee_skills", "employee_id", "employees", "employee_id", 0, None),
    ("employee_skills", "skill_id", "skills", "skill_id", 0, None), ("aircraft", "aircraft_type", "aircraft_types", "aircraft_type", 0, None),
    ("aircraft", "home_hub", "hubs", None, 0, None), ("aircraft_types", "pilot_type_rating_skill", "skills", "skill_id", 0, None),
    ("aircraft_types", "engineer_type_skill", "skills", "skill_id", 0, None), ("flights", "aircraft_tail", "aircraft", "tail_number", 1, None),
    ("flights", "aircraft_type", "aircraft_types", "aircraft_type", 0, None), ("flights", "origin", "airports", "airport_iata", 0, None),
    ("flights", "destination", "airports", "airport_iata", 0, None), ("flights", "crew_base_hub", "hubs", None, 0, None),
    ("flights", "dep_gate_id", "airport_gates", "gate_id", 1, None), ("flights", "flight_number", "flight_schedule", "flight_number", 0, None),
    ("flight_schedule", "origin", "airports", "airport_iata", 0, None), ("flight_schedule", "destination", "airports", "airport_iata", 0, None),
    ("flight_schedule", "aircraft_type", "aircraft_types", "aircraft_type", 0, None), ("flight_schedule", "crew_base_hub", "hubs", None, 0, None),
    ("flight_crew_assignments", "flight_id", "flights", "flight_id", 0, None), ("flight_crew_assignments", "employee_id", "employees", "employee_id", 1, None),
    ("availability_events", "employee_id", "employees", "employee_id", 0, None), ("availability_events", "training_session_id", "training_sessions", "session_id", 1, None),
    ("training_enrollments", "session_id", "training_sessions", "session_id", 0, None), ("training_enrollments", "employee_id", "employees", "employee_id", 0, None),
    ("training_sessions", "skill_id_granted", "skills", "skill_id", 1, None), ("training_sessions", "instructor_skill_id", "skills", "skill_id", 1, None),
    ("training_sessions", "hub", "hubs", None, 0, None), ("maintenance_activities", "tail_number", "aircraft", "tail_number", 0, None),
    ("maintenance_activities", "facility_id", "maintenance_facilities", "facility_id", 0, None), ("maintenance_activities", "hub", "hubs", None, 0, None),
    ("maintenance_requirements", "activity_id", "maintenance_activities", "activity_id", 0, None),
    ("maintenance_requirements", "required_license_skill", "skills", "skill_id", 0, None), ("maintenance_requirements", "required_type_skill", "skills", "skill_id", 1, None),
    ("maintenance_assignments", "activity_id", "maintenance_activities", "activity_id", 0, None),
    ("maintenance_assignments", "requirement_id", "maintenance_requirements", "requirement_id", 0, None),
    ("maintenance_assignments", "employee_id", "employees", "employee_id", 1, None), ("maintenance_facilities", "hub", "hubs", None, 0, None),
    ("airport_gates", "airport", "hubs", None, 0, None), ("disruption_flight_impacts", "disruption_id", "disruptions", "disruption_id", 0, None),
    ("disruption_flight_impacts", "flight_id", "flights", "flight_id", 0, None), ("disruptions", "hub", "hubs", None, 0, None),
    ("new_route_requirements", "route_launch_id", "new_route_launches", "route_launch_id", 0, None),
    ("new_route_requirements", "required_skill_id", "skills", "skill_id", 1, None), ("new_route_launches", "origin", "hubs", None, 0, None),
    ("new_route_launches", "destination", "airports", "airport_iata", 0, None), ("new_route_launches", "aircraft_type", "aircraft_types", "aircraft_type", 0, None),
    ("contractors", "home_hub", "hubs", None, 0, None), ("contractors", "skills", "skills", "skill_id", 0, "|"),
    ("service_requirements", "aircraft_type", "aircraft_types", "aircraft_type", 0, None), ("service_requirements", "required_skill_id", "skills", "skill_id", 1, None),
    ("special_events", "hub", "hubs", None, 0, None), ("candidate_hubs", "airport", "airports", "airport_iata", 0, None),
    ("network_plan_monthly", "hub", "hubs", None, 0, None), ("monthly_operations_history", "hub", "hubs", None, 0, None), ("budgets", "hub", "hubs", None, 0, None),
    ("maintenance_facilities", "supported_families", "aircraft_types", "family", 0, "|"),
]


def test_tables_match_row_counts_file(T, counts):
    assert set(T.names) == set(counts), f"differ: {set(T.names) ^ set(counts)}"
    wrong = {k: (T[k].height, v) for k, v in counts.items() if T[k].height != v}
    assert not wrong, f"(csv rows, expected): {wrong}"


def test_no_empty_tables(T):
    assert [n for n in T.names if T[n].height == 0] == []


def test_json_extras_exist(root):
    for name in ("scenarios", "hubs_nested", "contractors"):
        assert json.loads((root / "json" / f"{name}.json").read_text(encoding="utf-8")), name


def _json_tables(T, counts):
    return [n for n in counts if counts[n] <= JSON_MAX_ROWS and n != "contractors"]


def test_json_present_exactly_for_small_tables(root, counts):
    for n, c in counts.items():
        has = (root / "json" / f"{n}.json").exists()
        assert has == (c <= JSON_MAX_ROWS), f"{n}: rows={c} json_exists={has}"


def test_json_matches_csv(T, root, counts):
    bad = []
    for n in _json_tables(T, counts):
        js = json.loads((root / "json" / f"{n}.json").read_text(encoding="utf-8"))
        csv = T[n]
        if len(js) != csv.height: bad.append(f"{n}: rows json={len(js)} csv={csv.height}"); continue
        if list(js[0]) != csv.columns: bad.append(f"{n}: columns differ {list(js[0])} vs {csv.columns}"); continue
        for col in csv.columns:
            want = csv[col].to_list(); got = [None if r[col] is None else str(r[col]) for r in js]
            diff = [(i, w, g) for i, (w, g) in enumerate(zip(want, got)) if w != g and not _num_eq(w, g)]
            if diff: bad.append(f"{n}.{col}: {len(diff)} diffs, first {diff[0]}"); break
    assert not bad, "\n".join(bad)


def _num_eq(a, b):
    try: return float(a) == float(b)
    except (TypeError, ValueError): return False


@pytest.mark.parametrize("table", sorted(PK))
def test_primary_key_unique_and_not_null(T, table):
    df = T[table]; k = PK[table]
    none(df.filter(pl.any_horizontal(pl.col(k).is_null())), f"{table}: null key")
    none(df.filter(pl.struct(k).is_duplicated()), f"{table}: duplicate key {k}")


@pytest.mark.parametrize("child,col,parent,pcol,nullable,sep", FK, ids=[f"{c}.{col}" for c, col, *_ in FK])
def test_foreign_key(T, child, col, parent, pcol, nullable, sep):
    pk = (T["airports"].filter(pl.col("is_hub") == "1")["airport_iata"] if parent == "hubs" else T[parent][pcol]).unique()
    vals = T[child].select(pl.col(col))
    if not nullable: none(vals.filter(pl.col(col).is_null()), f"{child}.{col} null")
    vals = vals.drop_nulls()
    if sep: vals = vals.select(pl.col(col).str.split(sep).explode())
    none(vals.filter(~pl.col(col).is_in(pk.implode())).unique(), f"{child}.{col} -> {parent} dangling")
