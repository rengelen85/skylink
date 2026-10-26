"""Reference data: airports, aircraft types, skills, calendar, gates, facilities, weekly schedule."""
import math
from datetime import date, timedelta

import polars as pl

from helpers import D, none


def hav_expr(la1, lo1, la2, lo2):
    r = math.pi / 180
    a = ((pl.col(la2) - pl.col(la1)) * r / 2).sin() ** 2 + (pl.col(la1) * r).cos() * (pl.col(la2) * r).cos() * ((pl.col(lo2) - pl.col(lo1)) * r / 2).sin() ** 2
    return 6371 * 2 * a.sqrt().arcsin()


def test_fifteen_hubs_and_65_airports(T):
    a = T["airports"]
    assert a.filter(pl.col("is_hub") == "1").height == 15 and a.height == 65


def test_airports_sane(T):
    a = T["airports"].with_columns(pl.col("latitude").cast(pl.Float64), pl.col("longitude").cast(pl.Float64))
    none(a.filter(~pl.col("latitude").is_between(-90, 90) | ~pl.col("longitude").is_between(-180, 180) | ~pl.col("timezone").str.contains("/")), "coordinates/timezone")
    none(a.filter(~pl.col("airport_iata").str.contains(r"^[A-Z]{3}$")), "IATA code format")


def test_aircraft_types(T):
    t = T["aircraft_types"].with_columns(pl.col("seats", "fleet_size", "range_km", "min_cabin_crew").cast(pl.Int64))
    assert t["fleet_size"].sum() == 650
    none(t.filter((pl.col("seats") <= 0) | (pl.col("range_km") <= 0)), "non-positive specs")
    exp = (pl.col("seats") / 50).ceil().cast(pl.Int64) + (pl.col("body_type") == "wide").cast(pl.Int64)
    none(t.filter(pl.col("min_cabin_crew") != exp), "min_cabin_crew rule: ceil(seats/50) + 1 for wide-body")
    sk = T["skills"].select("skill_id", "category")
    j = t.join(sk, left_on="pilot_type_rating_skill", right_on="skill_id").join(sk, left_on="engineer_type_skill", right_on="skill_id", suffix="_e")
    none(j.filter((pl.col("category") != "AIRCRAFT_TYPE_RATING") | (pl.col("category_e") != "MAINTENANCE_TYPE_ENDORSEMENT")), "skill categories")


def test_skills_catalog(T):
    s = T["skills"]
    assert s.height == 62
    none(s.filter(pl.col("validity_months").cast(pl.Int64, strict=False) <= 0), "validity")
    none(s.filter(pl.col("renewal_course_code").is_not_null() & pl.col("validity_months").is_null()), "renewal course on a non-expiring skill")


def test_calendar_contiguous_and_consistent(T):
    c = T["calendar"].with_columns(d=D("date")).with_columns(pl.col("year", "month", "quarter", "iso_week", "day_of_week", "is_weekend").cast(pl.Int64))
    assert c["d"].to_list() == [date(2024, 1, 1) + timedelta(days=i) for i in range(1461)]
    none(c.filter((pl.col("d").dt.weekday() != pl.col("day_of_week")) | (pl.col("d").dt.month() != pl.col("month")) | (pl.col("d").dt.year() != pl.col("year"))
                  | ((pl.col("d").dt.weekday() >= 6).cast(pl.Int64) != pl.col("is_weekend")) | (pl.col("d").dt.quarter() != pl.col("quarter"))
                  | (pl.col("d").dt.week() != pl.col("iso_week"))), "calendar derived fields")
    none(c.filter(~pl.col("seasonal_demand_index").cast(pl.Float64).is_between(0, 2, closed="none")), "seasonal index")


def test_gates(T):
    g = T["airport_gates"]
    none(g.filter(pl.col("gate_id") != pl.col("airport") + "-G" + pl.col("gate_number").str.zfill(3)), "gate id format")
    none(g.filter(~pl.col("gate_type").is_in(["CONTACT", "REMOTE_STAND"]) | ~pl.col("max_body_type").is_in(["WIDE", "NARROW"])), "gate enums")


def test_facilities(T):
    f = T["maintenance_facilities"]
    line = f.filter(pl.col("facility_type") == "LINE_MAINTENANCE").group_by("hub").len()
    assert line.height == 15 and (line["len"] == 1).all(), "exactly one line-maintenance station per hub"
    none(f.filter((pl.col("hangar_bays").cast(pl.Int64) <= 0) | (pl.col("labor_capacity_hours_per_day").cast(pl.Int64) <= 0)), "capacity")


# ---------------------------------------------------------------- weekly schedule
def _sched(T):
    a = T["airports"].select("airport_iata", pl.col("latitude").cast(pl.Float64), pl.col("longitude").cast(pl.Float64), is_hub="is_hub")
    t = T["aircraft_types"].select("aircraft_type", pl.col("range_km").cast(pl.Int64), pl.col("cruise_speed_kmh").cast(pl.Int64))
    return (T["flight_schedule"].join(a, left_on="origin", right_on="airport_iata").join(a, left_on="destination", right_on="airport_iata", suffix="_d")
            .join(t, on="aircraft_type").with_columns(pl.col("block_minutes", "distance_km", "dep_day_offset").cast(pl.Int64)))


def test_schedule_basics(T):
    s = _sched(T)
    none(s.filter((pl.col("origin") == pl.col("destination")) | ((pl.col("is_hub") != "1") & (pl.col("is_hub_d") != "1"))), "route must touch a hub")
    none(s.filter(pl.col("days_of_week").str.contains("[^1-7]") | (pl.col("days_of_week").str.len_chars() == 0)), "days_of_week chars")
    none(s.filter(pl.col("days_of_week").str.split("").list.eval(pl.element().filter(pl.element() != "")).list.sort() != pl.col("days_of_week").str.split("").list.eval(pl.element().filter(pl.element() != ""))),
         "days_of_week not sorted")
    none(s.filter(~pl.col("scheduled_dep_time_utc").str.contains(r"^([01]\d|2[0-3]):[0-5]\d$") | (pl.col("dep_day_offset") < 0)), "dep time")
    none(s.filter((pl.col("season") != "W26/27") | (D("valid_from") >= D("valid_to"))), "season window")


def test_schedule_distance_matches_coordinates(T):
    s = _sched(T).with_columns(h=hav_expr("latitude", "longitude", "latitude_d", "longitude_d"))
    none(s.filter((pl.col("h") - pl.col("distance_km")).abs() > 2), "distance_km vs haversine")


def test_schedule_aircraft_range_and_block_time(T):
    s = _sched(T)
    none(s.filter(pl.col("distance_km") > pl.col("range_km")), "distance beyond aircraft range")
    exp = pl.col("distance_km") / pl.col("cruise_speed_kmh") * 60 + 32
    none(s.filter((pl.col("block_minutes") - exp).abs() > 0.2 * pl.col("block_minutes") + 60), "block time implausible for distance")


def test_rotation_pairs(T):
    s = T["flight_schedule"]
    g = s.group_by("rotation_pair_id").agg(n=pl.len(), o=pl.col("origin"), d=pl.col("destination"), days=pl.col("days_of_week").n_unique(),
                                           typ=pl.col("aircraft_type").n_unique(), base=pl.col("crew_base_hub").n_unique(), base0=pl.col("crew_base_hub").first())
    none(g.filter((pl.col("n") != 2) | (pl.col("days") != 1) | (pl.col("typ") != 1) | (pl.col("base") != 1)
                  | (pl.col("o").list.get(0) != pl.col("d").list.get(1)) | (pl.col("d").list.get(0) != pl.col("o").list.get(1))), "pairs must be 2 mirrored legs")
    none(s.filter(pl.col("crew_base_hub") != pl.col("origin")).join(s.group_by("rotation_pair_id").agg(first=pl.col("flight_number").min()), on="rotation_pair_id")
         .filter(pl.col("flight_number") == pl.col("first")), "outbound leg departs from its crew base")


def test_about_1200_flights_per_day(T):
    per_day = sum(len(d) / 7 for d in T["flight_schedule"]["days_of_week"])
    assert 1150 <= per_day <= 1250, per_day
