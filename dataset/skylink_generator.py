#!/usr/bin/env python3
"""SkyLink Airways - synthetic hackathon dataset generator (deterministic, seed=2026).
Reference date ("today") = Monday 2026-10-26. IATA winter season W26/27 started 2026-10-25."""
import os, math, random, json, csv, bisect
from datetime import date, datetime, timedelta
from collections import defaultdict

random.seed(2026)
OUT = os.path.dirname(os.path.abspath(__file__)); CSV_DIR = f"{OUT}/csv"; JSON_DIR = f"{OUT}/json"
for p in (CSV_DIR, JSON_DIR): os.makedirs(p, exist_ok=True)

TODAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 8, 26)        # UTC
EPOCH = datetime(2026, 10, 26)
FLIGHT_DAYS, ROSTER_DAYS = 28, 14
HIST_START, PLAN_END = date(2026, 7, 1), date(2027, 10, 31)

def M(dt): return int((dt - EPOCH).total_seconds() // 60)
def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
def rc(items, weights): return random.choices(items, weights=weights)[0]
def allocate(total, weights):
    s = sum(weights.values()); raw = {k: total * w / s for k, w in weights.items()}
    base = {k: int(v) for k, v in raw.items()}; rem = total - sum(base.values())
    for k in sorted(raw, key=lambda k: raw[k] - base[k], reverse=True)[:rem]: base[k] += 1
    return base
def rdate(a, b): return a + timedelta(days=random.randint(0, (b - a).days))
def last_sunday(y, m):
    d = date(y, m, 31) if m in (3, 10) else date(y, m, 28)
    while d.isoweekday() != 7: d -= timedelta(days=1)
    return d

T = {}   # table name -> list[dict]

# =====================================================================  AIRPORTS
HUBS = [
 ("AMS","Amsterdam Schiphol","Amsterdam","NL",52.31,4.76,"Europe/Amsterdam",14),
 ("FRA","Frankfurt Airport","Frankfurt","DE",50.03,8.57,"Europe/Berlin",13),
 ("MUC","Munich Airport","Munich","DE",48.35,11.79,"Europe/Berlin",11),
 ("CDG","Paris Charles de Gaulle","Paris","FR",49.01,2.55,"Europe/Paris",11),
 ("MAD","Madrid Barajas","Madrid","ES",40.47,-3.56,"Europe/Madrid",9),
 ("FCO","Rome Fiumicino","Rome","IT",41.80,12.25,"Europe/Rome",7),
 ("BCN","Barcelona El Prat","Barcelona","ES",41.30,2.08,"Europe/Madrid",6),
 ("LIS","Lisbon Humberto Delgado","Lisbon","PT",38.78,-9.14,"Europe/Lisbon",6),
 ("VIE","Vienna Schwechat","Vienna","AT",48.11,16.57,"Europe/Vienna",5),
 ("ZRH","Zurich Airport","Zurich","CH",47.46,8.55,"Europe/Zurich",5),
 ("CPH","Copenhagen Kastrup","Copenhagen","DK",55.62,12.65,"Europe/Copenhagen",4),
 ("ARN","Stockholm Arlanda","Stockholm","SE",59.65,17.92,"Europe/Stockholm",3),
 ("WAW","Warsaw Chopin","Warsaw","PL",52.17,20.97,"Europe/Warsaw",3),
 ("ATH","Athens Venizelos","Athens","GR",37.94,23.94,"Europe/Athens",3),
 ("DUB","Dublin Airport","Dublin","IE",53.43,-6.27,"Europe/Dublin",3),
]
OUTS = [
("LHR","London","GB",51.47,-0.45,"Europe/London",5),("MAN","Manchester","GB",53.35,-2.27,"Europe/London",2),
("EDI","Edinburgh","GB",55.95,-3.37,"Europe/London",2),("BRU","Brussels","BE",50.90,4.48,"Europe/Brussels",3),
("DUS","Dusseldorf","DE",51.29,6.77,"Europe/Berlin",2),("HAM","Hamburg","DE",53.63,9.99,"Europe/Berlin",2),
("BER","Berlin","DE",52.36,13.50,"Europe/Berlin",3),("MXP","Milan","IT",45.63,8.72,"Europe/Rome",3),
("NAP","Naples","IT",40.88,14.29,"Europe/Rome",1.5),("VCE","Venice","IT",45.51,12.35,"Europe/Rome",1.5),
("PMI","Palma de Mallorca","ES",39.55,2.74,"Europe/Madrid",3),("AGP","Malaga","ES",36.67,-4.50,"Europe/Madrid",2.5),
("SVQ","Seville","ES",37.42,-5.89,"Europe/Madrid",1.2),("VLC","Valencia","ES",39.49,-0.48,"Europe/Madrid",1.5),
("OPO","Porto","PT",41.24,-8.68,"Europe/Lisbon",2),("FAO","Faro","PT",37.01,-7.97,"Europe/Lisbon",1.5),
("NCE","Nice","FR",43.66,7.22,"Europe/Paris",2),("LYS","Lyon","FR",45.73,5.08,"Europe/Paris",1.5),
("GVA","Geneva","CH",46.24,6.11,"Europe/Zurich",2),("PRG","Prague","CZ",50.10,14.26,"Europe/Prague",2.5),
("BUD","Budapest","HU",47.44,19.26,"Europe/Budapest",2),("OTP","Bucharest","RO",44.57,26.09,"Europe/Bucharest",1.5),
("SOF","Sofia","BG",42.70,23.41,"Europe/Sofia",1),("BEG","Belgrade","RS",44.82,20.31,"Europe/Belgrade",1),
("ZAG","Zagreb","HR",45.74,16.07,"Europe/Zagreb",1.2),("HEL","Helsinki","FI",60.32,24.96,"Europe/Helsinki",2),
("OSL","Oslo","NO",60.19,11.10,"Europe/Oslo",2),("GOT","Gothenburg","SE",57.66,12.28,"Europe/Stockholm",1),
("KEF","Reykjavik","IS",63.99,-22.62,"Atlantic/Reykjavik",0.8),("RIX","Riga","LV",56.92,23.97,"Europe/Riga",1),
("TLL","Tallinn","EE",59.41,24.83,"Europe/Tallinn",0.8),("VNO","Vilnius","LT",54.63,25.29,"Europe/Vilnius",0.8),
("KRK","Krakow","PL",50.08,19.78,"Europe/Warsaw",1.2),("IST","Istanbul","TR",41.26,28.74,"Europe/Istanbul",3),
("SKG","Thessaloniki","GR",40.52,22.97,"Europe/Athens",1),("HER","Heraklion","GR",35.34,25.18,"Europe/Athens",1.2),
("LCA","Larnaca","CY",34.88,33.62,"Asia/Nicosia",1),("MLA","Malta","MT",35.86,14.50,"Europe/Malta",1),
("TLV","Tel Aviv","IL",32.01,34.89,"Asia/Jerusalem",1.2),("CAI","Cairo","EG",30.12,31.41,"Africa/Cairo",1),
("CMN","Casablanca","MA",33.37,-7.59,"Africa/Casablanca",1),("DXB","Dubai","AE",25.25,55.36,"Asia/Dubai",1.2),
("JFK","New York","US",40.64,-73.78,"America/New_York",1.6),("BOS","Boston","US",42.36,-71.01,"America/New_York",0.9),
("YYZ","Toronto","CA",43.68,-79.63,"America/Toronto",0.8),("ORD","Chicago","US",41.98,-87.90,"America/Chicago",0.8),
("MIA","Miami","US",25.79,-80.29,"America/New_York",0.7),("DEL","Delhi","IN",28.56,77.10,"Asia/Kolkata",0.8),
("NRT","Tokyo","JP",35.77,140.39,"Asia/Tokyo",0.6),("GRU","Sao Paulo","BR",-23.43,-46.47,"America/Sao_Paulo",0.7),
]
AP = {}
for i, n, c, cc, la, lo, tz, w in HUBS:
    AP[i] = dict(iata=i, name=n, city=c, country=cc, lat=la, lon=lo, tz=tz, is_hub=True, w=w)
for i, c, cc, la, lo, tz, w in OUTS:
    AP[i] = dict(iata=i, name=f"{c} Airport", city=c, country=cc, lat=la, lon=lo, tz=tz, is_hub=False, w=w)
HUB_W = {h[0]: h[7] for h in HUBS}; HUB_CODES = list(HUB_W)
HUB_CC = {h: AP[h]["country"] for h in HUB_CODES}
T["airports"] = [dict(airport_iata=a["iata"], name=a["name"], city=a["city"], country=a["country"],
                      latitude=a["lat"], longitude=a["lon"], timezone=a["tz"], is_hub=int(a["is_hub"])) for a in AP.values()]

def hav(a, b):
    p1, p2 = math.radians(AP[a]["lat"]), math.radians(AP[b]["lat"])
    dl = math.radians(AP[b]["lon"] - AP[a]["lon"]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))

# =====================================================================  AIRCRAFT TYPES
ACT = {
 "A220-300": dict(fam="A220",  seats=148, n=90,  speed=780, rng=6000,  body="narrow", tr="TR_A220",   mt="MT_A220"),
 "E195-E2":  dict(fam="E2",    seats=132, n=60,  speed=760, rng=4800,  body="narrow", tr="TR_E2",     mt="MT_E2"),
 "A320neo":  dict(fam="A320FAM",seats=180, n=220, speed=800, rng=6300,  body="narrow", tr="TR_A320FAM",mt="MT_A320FAM"),
 "A321neo":  dict(fam="A320FAM",seats=220, n=130, speed=800, rng=7400,  body="narrow", tr="TR_A320FAM",mt="MT_A320FAM"),
 "A330-900": dict(fam="A330",  seats=290, n=55,  speed=850, rng=12000, body="wide",   tr="TR_A330",   mt="MT_A330"),
 "A350-900": dict(fam="A350",  seats=325, n=50,  speed=870, rng=15000, body="wide",   tr="TR_A350",   mt="MT_A350"),
 "B787-9":   dict(fam="B787",  seats=296, n=45,  speed=870, rng=14000, body="wide",   tr="TR_B787",   mt="MT_B787"),
}
assert sum(v["n"] for v in ACT.values()) == 650
FAMS = ["A220", "E2", "A320FAM", "A330", "A350", "B787"]
FAM_TR = {f: f"TR_{f}" for f in FAMS}; FAM_MT = {f: f"MT_{f}" for f in FAMS}
for k, v in ACT.items():
    v["cabin_min"] = math.ceil(v["seats"] / 50) + (1 if v["body"] == "wide" else 0)
T["aircraft_types"] = [dict(aircraft_type=k, family=v["fam"], body_type=v["body"], seats=v["seats"], fleet_size=v["n"],
        cruise_speed_kmh=v["speed"], range_km=v["rng"], pilot_type_rating_skill=v["tr"], engineer_type_skill=v["mt"],
        min_cabin_crew=v["cabin_min"]) for k, v in ACT.items()]

# =====================================================================  FLIGHT SCHEDULE TEMPLATES
LONG_HUB = {"AMS", "FRA", "MUC", "CDG", "MAD", "LIS", "ZRH", "FCO"}
dest_codes = list(AP); dest_w = [AP[a]["w"] * (0.35 if AP[a]["is_hub"] else 1) for a in dest_codes]
def pick_type(d):
    if d < 900:  return rc(["A220-300", "E195-E2", "A320neo"], [40, 38, 22])
    if d < 2500: return rc(["A320neo", "A321neo", "A220-300", "E195-E2"], [45, 30, 15, 10])
    if d < 4300: return rc(["A321neo", "A320neo", "A330-900", "A220-300"], [50, 25, 20, 5])
    return rc(["A350-900", "B787-9", "A330-900"], [42, 35, 23])
def ppf(block): return 2 if block < 480 else (3 if block < 780 else 4)
MASKS = [("1234567", 78), ("12345", 6), ("123457", 5), ("1357", 3), ("12346", 3), ("246", 2), ("567", 1.5), ("135", 1.5)]
BANKS = [(5.5, 10), (7.5, 16), (9, 10), (11, 10), (13, 10), (15.5, 12), (17.5, 14), (19.5, 8)]
templates = []; cum = 0.0; fn = 100; pi = 0
while cum < 1200:
    o = rc(HUB_CODES, [HUB_W[h] for h in HUB_CODES])
    for _ in range(200):
        dd = rc(dest_codes, dest_w)
        if dd == o: continue
        dist = hav(o, dd)
        if dist < 250 or (dist > 4300 and o not in LONG_HUB): continue
        break
    typ = pick_type(dist); spec = ACT[typ]
    blk = dist / spec["speed"] * 60 + 32
    out_blk = blk * (1.09 if AP[dd]["lon"] < -30 and AP[o]["lon"] > -30 else 1.0) + random.randint(-5, 8)
    ret_blk = blk * (0.92 if AP[dd]["lon"] < -30 and AP[o]["lon"] > -30 else 1.0) + random.randint(-5, 8)
    out_blk, ret_blk = int(round(out_blk)), int(round(ret_blk))
    c = rc([b[0] for b in BANKS], [b[1] for b in BANKS])
    dep = int(round((c * 60 + random.randint(-60, 60)) / 5) * 5)
    turn = random.randint(55, 120) if spec["body"] == "narrow" else random.randint(110, 220)
    ret_dep = dep + out_blk + turn
    mask = rc([m[0] for m in MASKS], [m[1] for m in MASKS])
    pi += 1; fn += random.choice([2, 2, 2, 4, 6])
    for (n_, a_, b_, dm, bl) in ((fn, o, dd, dep, out_blk), (fn + 1, dd, o, ret_dep, ret_blk)):
        templates.append(dict(flight_number=f"SL{n_}", origin=a_, destination=b_, dep_min=dm, block=bl, typ=typ,
                              mask=mask, crew_base=o, pair_id=f"P{pi:04d}", dist=int(dist)))
    cum += 2 * len(mask) / 7
T["flight_schedule"] = [dict(flight_number=t["flight_number"], origin=t["origin"], destination=t["destination"],
        scheduled_dep_time_utc=f"{(t['dep_min'] % 1440) // 60:02d}:{t['dep_min'] % 60:02d}", dep_day_offset=t["dep_min"] // 1440,
        block_minutes=t["block"], distance_km=t["dist"], aircraft_type=t["typ"], days_of_week=t["mask"],
        crew_base_hub=t["crew_base"], rotation_pair_id=t["pair_id"], season="W26/27",
        valid_from="2026-10-25", valid_to="2027-03-27") for t in templates]
FPD = lambda t: len(t["mask"]) / 7

# demand matrices per hub
pil_dem = defaultdict(float); cab_dem = defaultdict(float); gnd_w = defaultdict(float); fl_touch = defaultdict(float)
type_cell = defaultdict(float)
for t in templates:
    f = FPD(t); hrs = t["block"] / 60; sp = ACT[t["typ"]]
    pil_dem[(t["crew_base"], sp["fam"])] += f * hrs * ppf(t["block"]) * 30.4
    cab_dem[(t["crew_base"], sp["body"])] += f * hrs * sp["cabin_min"] * 30.4
    type_cell[(t["typ"], t["crew_base"])] += f * (t["block"] + 90) / 60
    for ap_, wgt in ((t["origin"], 1.0), (t["destination"], 0.6)):
        if AP[ap_]["is_hub"]: gnd_w[ap_] += f * wgt
    for ap_ in {t["origin"], t["destination"]}:
        if AP[ap_]["is_hub"]: fl_touch[ap_] += f
print("avg flights/day:", round(sum(FPD(t) for t in templates), 1), " templates:", len(templates))

# =====================================================================  AIRCRAFT
PFX = {"NL": ("PH-", 3), "DE": ("D-A", 3), "FR": ("F-H", 3), "ES": ("EC-", 3), "IT": ("I-", 4), "PT": ("CS-", 3), "AT": ("OE-", 3),
       "CH": ("HB-", 3), "DK": ("OY-", 3), "SE": ("SE-", 3), "PL": ("SP-", 3), "GR": ("SX-", 3), "IE": ("EI-", 3)}
LET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"; used_tails = set(); aircraft = []
DELIV = {"A220": 2019, "E2": 2019, "A320FAM": 2017, "A330": 2019, "A350": 2016, "B787": 2016}
for typ, spec in ACT.items():
    cells = allocate(spec["n"], {h: type_cell.get((typ, h), 0) + 0.01 for h in HUB_CODES if type_cell.get((typ, h), 0) > 0})
    for hub, cnt in cells.items():
        for _ in range(cnt):
            pre, ln = PFX[HUB_CC[hub]]
            while True:
                tail = pre + "".join(random.choice(LET) for _ in range(ln))
                if tail not in used_tails: used_tails.add(tail); break
            dd = rdate(date(DELIV[spec["fam"]], 1, 1), date(2026, 8, 31))
            yrs = (TODAY - dd).days / 365
            aircraft.append(dict(tail_number=tail, aircraft_type=typ, family=spec["fam"], seats=spec["seats"], home_hub=hub,
                                 delivery_date=dd.isoformat(), total_flight_hours=int(yrs * random.randint(2800, 3800)),
                                 total_cycles=int(yrs * random.randint(1100, 1700))))
random.shuffle(aircraft); AC = {a["tail_number"]: a for a in aircraft}
print("aircraft:", len(aircraft))

# =====================================================================  FACILITIES & GATES
BASES = {"AMS": 8, "FRA": 6, "MUC": 6, "CDG": 6, "MAD": 5, "LIS": 4}
BASE_FAMS = {"AMS": FAMS, "FRA": ["A320FAM", "A330", "A350", "E2"], "MUC": ["A320FAM", "A350", "A220"],
             "CDG": ["A320FAM", "A330", "B787", "A220"], "MAD": ["A320FAM", "A330", "E2", "B787"], "LIS": ["A320FAM", "A220", "E2", "A330"]}
facilities = []
for h in HUB_CODES:
    bays = 2 + HUB_W[h] // 4
    facilities.append(dict(facility_id=f"MF-{h}-LINE", hub=h, name=f"{AP[h]['city']} Line Maintenance", facility_type="LINE_MAINTENANCE",
                           hangar_bays=bays, supported_families="|".join(FAMS), labor_capacity_hours_per_day=bays * 90))
    if h in BASES:
        facilities.append(dict(facility_id=f"MF-{h}-BASE", hub=h, name=f"{AP[h]['city']} Base Maintenance Hangar", facility_type="BASE_MAINTENANCE",
                               hangar_bays=BASES[h], supported_families="|".join(BASE_FAMS[h]), labor_capacity_hours_per_day=BASES[h] * 260))
T["maintenance_facilities"] = facilities
gates = []; GATES_BY_HUB = defaultdict(list)
for h in HUB_CODES:
    n = max(24, int(HUB_W[h] * 7 + 10)); nt = 1 if n < 35 else (2 if n < 60 else 3)
    for k in range(n):
        g = dict(gate_id=f"{h}-G{k+1:03d}", airport=h, terminal=f"T{k % nt + 1}", gate_number=k + 1,
                 gate_type="CONTACT" if random.random() < 0.62 else "REMOTE_STAND",
                 max_body_type="WIDE" if random.random() < 0.28 else "NARROW")
        gates.append(g); GATES_BY_HUB[h].append(dict(id=g["gate_id"], wide=g["max_body_type"] == "WIDE", free=-10**9))
T["airport_gates"] = gates

# =====================================================================  MAINTENANCE ACTIVITIES (demand)
acts = []; act_n = 0
def add_act(tail, atype, desc, fac, start, end, mh, prio, aog=0):
    global act_n; act_n += 1
    st = "COMPLETED" if end < NOW else ("IN_PROGRESS" if start <= NOW else "PLANNED")
    acts.append(dict(activity_id=f"MX{act_n:06d}", tail_number=tail, activity_type=atype, description=desc, facility_id=fac,
                     hub=fac.split("-")[1], planned_start_utc=iso(start), planned_end_utc=iso(end), estimated_man_hours=int(mh),
                     priority=prio, status=st, aog_flag=aog, _s=start, _e=end))
bay_occ = defaultdict(int)
for a in aircraft:
    fam, spec_body = a["family"], ACT[a["aircraft_type"]]["body"]; wide = spec_body == "wide"
    iv = random.randint(105, 140); d = HIST_START + timedelta(days=random.randint(0, iv))
    while d <= PLAN_END:
        s = datetime(d.year, d.month, d.day, 22); e = s + timedelta(hours=31 if wide else 7)
        add_act(a["tail_number"], "A_CHECK", "Scheduled A-check (line maintenance, overnight)", f"MF-{a['home_hub']}-LINE", s, e,
                random.randint(160, 260) if wide else random.randint(90, 160), "ROUTINE")
        d += timedelta(days=iv + random.randint(-5, 5))
    cd = TODAY + timedelta(days=random.randint(-117, 613))
    if HIST_START <= cd <= PLAN_END:
        bases = [b for b in BASES if fam in BASE_FAMS[b]]
        base = a["home_hub"] if a["home_hub"] in bases else rc(bases, [BASES[b] for b in bases])
        dur = random.randint(22, 36) if wide else random.randint(14, 24)
        while cd <= PLAN_END and not all(bay_occ[(base, cd + timedelta(days=k))] < BASES[base] for k in range(dur)): cd += timedelta(days=1)
        if cd <= PLAN_END:   # no free bay window before the end of the plan -> no C-check is booked (never over-subscribe a hangar)
            for k in range(dur): bay_occ[(base, cd + timedelta(days=k))] += 1
            s = datetime(cd.year, cd.month, cd.day, 6); e = s + timedelta(days=dur)
            add_act(a["tail_number"], "C_CHECK", "Heavy maintenance C-check (base maintenance)", f"MF-{base}-BASE", s, e,
                    random.randint(9000, 16000) if wide else random.randint(4500, 7500), "ROUTINE")
DEFECTS = ["Hydraulic leak investigation", "Bird strike inspection", "Tyre and brake change", "Engine borescope inspection",
           "APU fault rectification", "Lightning strike inspection", "Avionics fault (FMS)", "Cabin pressurisation fault",
           "Landing gear sensor fault", "Cargo door actuator replacement", "Air-conditioning pack fault", "Windshield crack replacement"]
d = HIST_START
while d < TODAY:
    for _ in range(random.randint(5, 11)):
        a = random.choice(aircraft); s = datetime(d.year, d.month, d.day) + timedelta(minutes=random.randint(0, 1380))
        aog = int(random.random() < 0.12); dur = random.randint(10, 60) if aog else random.randint(2, 14)
        e = s + timedelta(hours=dur)
        if e >= NOW: e = NOW - timedelta(minutes=30)
        add_act(a["tail_number"], "UNSCHEDULED_DEFECT", random.choice(DEFECTS), f"MF-{a['home_hub']}-LINE", s, e,
                dur * random.randint(2, 5), "AOG" if aog else "HIGH", aog)
    d += timedelta(days=1)
c_inprog = {x["tail_number"] for x in acts if x["status"] == "IN_PROGRESS"}
cands = [a for a in aircraft if a["tail_number"] not in c_inprog]; random.shuffle(cands)
for a in cands[:12]:
    s = NOW - timedelta(hours=random.randint(6, 70)); e = NOW + timedelta(hours=random.randint(8, 100))
    add_act(a["tail_number"], "UNSCHEDULED_DEFECT", random.choice(DEFECTS) + " (AOG)", f"MF-{a['home_hub']}-LINE", s, e, random.randint(40, 200), "AOG", 1)
for a in cands[12:112]:
    s = datetime.combine(TODAY + timedelta(days=random.randint(1, 27)), datetime.min.time()) + timedelta(hours=22)
    add_act(a["tail_number"], "DEFERRED_DEFECT", "Rectification of MEL deferred defect", f"MF-{a['home_hub']}-LINE", s, s + timedelta(hours=7),
            random.randint(6, 40), "ROUTINE")
acts.sort(key=lambda x: x["_s"])
MX_UNAVAIL = defaultdict(list)
for x in acts:
    if x["status"] != "COMPLETED": MX_UNAVAIL[x["tail_number"]].append((M(x["_s"]), M(x["_e"])))
for a in aircraft:
    mine = [x for x in acts if x["tail_number"] == a["tail_number"]] if False else None
by_tail = defaultdict(list)
for x in acts: by_tail[x["tail_number"]].append(x)
for a in aircraft:
    L = by_tail[a["tail_number"]]
    ip = [x for x in L if x["status"] == "IN_PROGRESS"]
    a["status"] = "AOG" if any(x["aog_flag"] for x in ip) else ("IN_MAINTENANCE" if any(x["activity_type"] in ("C_CHECK", "A_CHECK") for x in ip) else "ACTIVE")
    for key, nm in (("A_CHECK", "a"), ("C_CHECK", "c")):
        done = [x for x in L if x["activity_type"] == key and x["status"] == "COMPLETED"]; nxt = [x for x in L if x["activity_type"] == key and x["status"] != "COMPLETED"]
        a[f"last_{nm}_check_date"] = max(x["planned_start_utc"] for x in done)[:10] if done else None
        a[f"next_{nm}_check_due"] = min(x["planned_start_utc"] for x in nxt)[:10] if nxt else None
    a["open_mel_items"] = random.choice([0, 0, 0, 1, 1, 2, 3])
T["aircraft"] = aircraft
print("maintenance activities:", len(acts))

# =====================================================================  FLIGHT INSTANCES
TAILS_BY_TYPE = defaultdict(list)
for a in aircraft:
    TAILS_BY_TYPE[a["aircraft_type"]].append(dict(tail=a["tail_number"], loc=a["home_hub"], free=-10**9, mx=MX_UNAVAIL.get(a["tail_number"], [])))
SEAS_LF = {1: .76, 2: .77, 3: .80, 4: .82, 5: .84, 6: .88, 7: .91, 8: .92, 9: .87, 10: .83, 11: .78, 12: .82}
DOW_LF = {1: 0.0, 2: -.03, 3: -.02, 4: .01, 5: .04, 6: -.02, 7: .04}
inst = []
for k in range(FLIGHT_DAYS):
    op = TODAY + timedelta(days=k); dow = op.isoweekday(); base = datetime(op.year, op.month, op.day)
    for t in templates:
        if str(dow) not in t["mask"]: continue
        sp = ACT[t["typ"]]; dep = base + timedelta(minutes=t["dep_min"]); arr = dep + timedelta(minutes=t["block"])
        lf = min(.99, max(.45, SEAS_LF[op.month] + DOW_LF[dow] + (0.03 if sp["body"] == "wide" else 0) + random.gauss(0, 0.05)))
        inst.append(dict(flight_id=f"{t['flight_number']}_{op:%Y%m%d}", flight_number=t["flight_number"], operating_date=op.isoformat(),
                         origin=t["origin"], destination=t["destination"], scheduled_dep_utc=iso(dep), scheduled_arr_utc=iso(arr),
                         block_minutes=t["block"], distance_km=t["dist"], aircraft_type=t["typ"], aircraft_tail=None, seats=sp["seats"],
                         booked_pax=int(sp["seats"] * lf), load_factor=round(lf, 3), crew_base_hub=t["crew_base"], rotation_pair_id=t["pair_id"],
                         status="SCHEDULED", dep_gate_id=None, _dm=M(dep), _am=M(arr), _body=sp["body"], _fam=sp["fam"], _date=op))
inst.sort(key=lambda f: f["_dm"])
no_tail = teleports = 0
for f in inst:
    turn = 40 if f["_body"] == "narrow" else 85
    best = best_any = None
    for t in TAILS_BY_TYPE[f["aircraft_type"]]:
        if t["free"] > f["_dm"]: continue
        if any(s < f["_am"] + 30 and e > f["_dm"] - 30 for s, e in t["mx"]): continue
        if t["loc"] == f["origin"]:
            if best is None or t["free"] < best["free"]: best = t
        elif best_any is None or t["free"] < best_any["free"]: best_any = t
    pick = best or best_any
    if pick is None: no_tail += 1; continue
    if pick is best_any: teleports += 1
    pick["free"] = f["_am"] + turn; pick["loc"] = f["destination"]; f["aircraft_tail"] = pick["tail"]
print(f"flights: {len(inst)}  no tail: {no_tail}  non-contiguous tail positions: {teleports}")
for f in inst:
    if f["_dm"] < M(NOW): f["status"] = "COMPLETED" if f["_am"] < M(NOW) else "AIRBORNE"
# gates
for f in inst:
    if f["origin"] in GATES_BY_HUB:
        for g in random.sample(GATES_BY_HUB[f["origin"]], len(GATES_BY_HUB[f["origin"]])):
            if g["free"] <= f["_dm"] - 70 and (g["wide"] or f["_body"] == "narrow"):
                g["free"] = f["_dm"] + 10; f["dep_gate_id"] = g["id"]; break

# =====================================================================  DISRUPTIONS
D_ = []
def add_dis(group, typ, hub, s, e, sev, desc, red):
    st = "RESOLVED" if e < NOW else ("ACTIVE" if s <= NOW else "FORECAST")
    D_.append(dict(disruption_id=f"DIS{len(D_)+1:03d}", event_group=group, disruption_type=typ, hub=hub, start_utc=iso(s), end_utc=iso(e),
                   severity=sev, status=st, airport_capacity_reduction_pct=red, description=desc, _s=s, _e=e))
dt_ = lambda y, m, d_, h=0: datetime(y, m, d_, h)
add_dis("Fog ZRH 26-Oct", "WEATHER_FOG", "ZRH", dt_(2026,10,26,5), dt_(2026,10,26,10)+timedelta(minutes=30), "MEDIUM", "Dense fog, low visibility procedures", 40)
for h, sev, red in (("AMS", "SEVERE", 70), ("FRA", "HIGH", 45), ("CPH", "MEDIUM", 30)):
    add_dis("Storm Aurelia", "WEATHER_STORM", h, dt_(2026,10,29,3), dt_(2026,10,30,2), sev, "Autumn windstorm, gusts >90 km/h, runway restrictions", red)
add_dis("French ATC action", "ATC_STRIKE", "CDG", dt_(2026,11,12,4), dt_(2026,11,12,20), "HIGH", "Air traffic control strike, ~30% overflight slot cuts", 30)
add_dis("Early snow Nordics", "WEATHER_SNOW", "ARN", dt_(2026,11,17,0), dt_(2026,11,18,12), "MEDIUM", "Snowfall, de-icing capacity constrained", 25)
add_dis("Early snow Nordics", "WEATHER_SNOW", "CPH", dt_(2026,11,17,6), dt_(2026,11,18,6), "LOW", "Light snowfall, de-icing required", 10)
add_dis("Italian ground handling strike", "GROUND_STRIKE", "FCO", dt_(2026,11,20,9), dt_(2026,11,20,17), "HIGH", "Ground handling strike (4 h window), partial staffing", 35)
add_dis("Baggage system outage", "IT_OUTAGE", "MUC", dt_(2026,11,5,6), dt_(2026,11,5,14), "MEDIUM", "Baggage handling system failure (forecast maintenance window)", 15)
for i in range(10):
    h = random.choice(HUB_CODES); s = datetime.combine(rdate(HIST_START, TODAY - timedelta(days=2)), datetime.min.time()) + timedelta(hours=random.randint(0, 20))
    ty = random.choice(["WEATHER_STORM", "WEATHER_FOG", "ATC_STRIKE", "IT_OUTAGE", "WEATHER_THUNDERSTORM"])
    add_dis(f"Past event {i+1}", ty, h, s, s + timedelta(hours=random.randint(3, 20)), random.choice(["LOW", "MEDIUM", "MEDIUM", "HIGH"]), f"Historical {ty.lower().replace('_',' ')} event", random.choice([10, 20, 30, 40]))
RISK = {"LOW": .10, "MEDIUM": .25, "HIGH": .50, "SEVERE": .80}; impacts = []
for dz in D_:
    if dz["status"] == "RESOLVED" and dz["_e"] < EPOCH: continue
    for f in inst:
        if dz["hub"] in (f["origin"], f["destination"]):
            dm = f["_dm"] if f["origin"] == dz["hub"] else f["_am"]
            if M(dz["_s"]) - 60 <= dm <= M(dz["_e"]) + 60:
                r = min(.99, RISK[dz["severity"]] * random.uniform(.6, 1.4))
                impacts.append(dict(disruption_id=dz["disruption_id"], flight_id=f["flight_id"],
                                    impact_type="CANCELLATION_RISK" if dz["severity"] in ("HIGH", "SEVERE") else "DELAY_RISK", risk_score=round(r, 2)))
                if dz["status"] == "ACTIVE" and f["_dm"] < M(NOW) + 600 and f["status"] != "COMPLETED" and random.random() < .35: f["status"] = "CANCELLED"
T["disruptions"] = [{k: v for k, v in d.items() if not k.startswith("_")} for d in D_]
T["disruption_flight_impacts"] = impacts
FL = {f["flight_id"]: f for f in inst}

# =====================================================================  SKILLS CATALOG
SK = []
def sk(sid, cat, name, months, roles, course=None, desc=""):
    SK.append(dict(skill_id=sid, category=cat, name=name, description=desc or name, validity_months=months, applicable_roles=roles, renewal_course_code=course))
TRN = {"A220": "Airbus A220", "E2": "Embraer E195-E2", "A320FAM": "Airbus A320 family (A320neo/A321neo)", "A330": "Airbus A330", "A350": "Airbus A350", "B787": "Boeing 787"}
for f in FAMS: sk(f"TR_{f}", "AIRCRAFT_TYPE_RATING", f"Type rating {TRN[f]}", 12, "Pilot", "SIM_PC", "Pilot type rating, renewed annually through a simulator proficiency check")
sk("PR_CAT3", "PILOT_RATING", "CAT II/III low-visibility approach", 12, "Pilot", "SIM_PC"); sk("PR_LVO", "PILOT_RATING", "Low Visibility Operations (LVTO)", 12, "Pilot", "SIM_PC")
sk("PR_ETOPS", "PILOT_RATING", "ETOPS / extended-range operations", 12, "Pilot", "SIM_PC"); sk("PR_TRI", "PILOT_RATING", "Type Rating Instructor", 36, "Pilot")
sk("PR_TRE", "PILOT_RATING", "Type Rating Examiner", 36, "Pilot")
sk("CQ_NARROW", "CABIN_QUALIFICATION", "Cabin type qualification narrow-body", 36, "Cabin Crew"); sk("CQ_WIDE", "CABIN_QUALIFICATION", "Cabin type qualification wide-body", 36, "Cabin Crew")
sk("CC_SEP", "CABIN_QUALIFICATION", "Safety & Emergency Procedures (annual)", 12, "Cabin Crew", "SEP"); sk("CC_FIRSTAID", "CABIN_QUALIFICATION", "Cabin first aid", 36, "Cabin Crew", "FIRSTAID")
sk("CC_PURSER", "CABIN_QUALIFICATION", "Purser / cabin lead qualification", None, "Cabin Crew")
sk("SC_AIRPORT_ID", "SECURITY_CLEARANCE", "Airport access ID (airside)", 60, "All"); sk("SC_AVSEC", "SECURITY_CLEARANCE", "Aviation security awareness", 36, "All", "AVSEC")
sk("SC_DG", "SECURITY_CLEARANCE", "Dangerous goods handling", 24, "Pilot|Cabin Crew|Ground Staff", "DG"); sk("SC_ENHANCED", "SECURITY_CLEARANCE", "Enhanced background-check clearance", 60, "Ground Staff|Operations Coordinator|Maintenance Engineer")
sk("MC_B1", "MAINTENANCE_CERTIFICATION", "Part-66 B1 licence (mechanical)", 60, "Maintenance Engineer"); sk("MC_B2", "MAINTENANCE_CERTIFICATION", "Part-66 B2 licence (avionics)", 60, "Maintenance Engineer")
sk("MC_C", "MAINTENANCE_CERTIFICATION", "Base maintenance certifying staff (C)", 60, "Maintenance Engineer"); sk("MC_TECH", "MAINTENANCE_CERTIFICATION", "Technician authorisation", 24, "Maintenance Engineer")
sk("MC_NDT", "MAINTENANCE_CERTIFICATION", "Non-destructive testing", 36, "Maintenance Engineer"); sk("MC_COMPOSITE", "MAINTENANCE_CERTIFICATION", "Composite repair", 36, "Maintenance Engineer")
for f in FAMS: sk(f"MT_{f}", "MAINTENANCE_TYPE_ENDORSEMENT", f"Engineer type endorsement {TRN[f]}", None, "Maintenance Engineer")
GCS = [("GC_RAMP", "Ramp handling"), ("GC_BAGGAGE", "Baggage handling"), ("GC_PUSHBACK", "Pushback / tow"), ("GC_DEICING", "De-icing operator"),
       ("GC_LOADCONTROL", "Load control & weight and balance"), ("GC_PRM", "Passengers with reduced mobility assistance"), ("GC_FUELING", "Aircraft fuelling"),
       ("GC_CHECKIN", "Check-in systems"), ("GC_GATE", "Gate / boarding"), ("GC_CLEANING", "Aircraft cleaning")]
for sid, nm in GCS: sk(sid, "GROUND_CERTIFICATION", nm, {"GC_DEICING": 12, "GC_LOADCONTROL": 24, "GC_PRM": 24}.get(sid, 24), "Ground Staff",
                       {"GC_DEICING": "DEICING", "GC_LOADCONTROL": "LOADCTRL", "GC_PRM": "PRM"}.get(sid))
for sid, nm in (("OC_DISPATCH", "Flight dispatcher licence"), ("OC_CREWCTRL", "Crew control certification"), ("OC_MXCTRL", "Maintenance control certification"),
                ("OC_DUTYMGR", "Duty manager certification"), ("OC_NETWORK", "Network control certification")): sk(sid, "OPS_CERTIFICATION", nm, 36, "Operations Coordinator")
LANGS = {"EN": "English", "DE": "German", "FR": "French", "ES": "Spanish", "IT": "Italian", "NL": "Dutch", "PT": "Portuguese", "DA": "Danish",
         "SV": "Swedish", "PL": "Polish", "EL": "Greek", "TR": "Turkish", "AR": "Arabic", "RU": "Russian", "ZH": "Chinese"}
for c, n in LANGS.items(): sk(f"LANG_{c}", "LANGUAGE", f"Language: {n}", None, "All", desc=f"{n} (CEFR level in employee_skills.level)")
SKD = {s["skill_id"]: s for s in SK}
T["skills"] = SK

# =====================================================================  EMPLOYEES
N_PIL = int(round(sum(pil_dem.values()) / (85 * 0.60 * 0.96))); N_CAB = int(round(sum(cab_dem.values()) / (90 * 0.60 * 0.96)))
N_MX, N_OPS = 7000, 2400; N_GND = 45000 - N_PIL - N_CAB - N_MX - N_OPS
print("headcount plan: pilots", N_PIL, "cabin", N_CAB, "ground", N_GND, "maint", N_MX, "ops", N_OPS)
HF = {("FCO", "Cabin Crew"): .80, ("BCN", "Pilot"): .86, ("ATH", "Ground Staff"): .78, ("WAW", "Pilot"): 1.18, ("ARN", "Ground Staff"): 1.15,
      ("MAD", "Maintenance Engineer"): .85, ("LIS", "Cabin Crew"): 1.12, ("CDG", "Operations Coordinator"): .85, ("DUB", "Pilot"): .90, ("VIE", "Cabin Crew"): .90}
f_ = lambda h, r: HF.get((h, r), 1.0) * random.uniform(.94, 1.06)
pil_cells = allocate(N_PIL, {k: v * f_(k[0], "Pilot") for k, v in pil_dem.items()})
cab_cells = allocate(N_CAB, {k: v * f_(k[0], "Cabin Crew") for k, v in cab_dem.items()})
gnd_cells = allocate(N_GND, {h: gnd_w[h] * f_(h, "Ground Staff") for h in HUB_CODES})
tails_at = defaultdict(int); tails_fam_at = defaultdict(lambda: defaultdict(int))
for a in aircraft: tails_at[a["home_hub"]] += 1; tails_fam_at[a["home_hub"]][a["family"]] += 1
mx_w = {h: (tails_at[h] + {"AMS": 80, "FRA": 60, "MUC": 60, "CDG": 60, "MAD": 50, "LIS": 40}.get(h, 0)) * f_(h, "Maintenance Engineer") for h in HUB_CODES}
mx_cells = allocate(N_MX, mx_w); ops_cells = allocate(N_OPS, {h: fl_touch[h] * f_(h, "Operations Coordinator") for h in HUB_CODES})
NAMES = {
 "NL": ("Daan Sem Lucas Finn Noah Emma Julia Sophie Lotte Anna Milan Thijs Bram Eva Fleur Sanne Joris Ruben Lars Iris", "de_Vries Jansen Bakker Visser Smit Meijer de_Boer Mulder de_Groot Bos Vos Peters Hendriks van_Dijk Dekker Brouwer"),
 "DE": ("Lukas Leon Felix Jonas Paul Anna Lena Marie Laura Julia Max Tim Nina Katrin Stefan Jan Sabine Moritz Hannah Tobias", "Muller Schmidt Schneider Fischer Weber Meyer Wagner Becker Hoffmann Schulz Koch Richter Klein Wolf Neumann Braun"),
 "FR": ("Lucas Hugo Louis Jules Camille Chloe Manon Lea Emma Nathan Theo Alice Antoine Claire Julien Margaux Pierre Oceane Mathieu Ines", "Martin Bernard Dubois Thomas Robert Richard Petit Durand Leroy Moreau Simon Laurent Lefebvre Michel Garcia Roux"),
 "ES": ("Pablo Hugo Daniel Alvaro Javier Lucia Sofia Carmen Marta Paula Diego Sergio Laura Elena Carlos Irene Adrian Raquel Ivan Nuria", "Garcia Rodriguez Gonzalez Fernandez Lopez Martinez Sanchez Perez Gomez Martin Jimenez Ruiz Hernandez Diaz Moreno Alvarez"),
 "IT": ("Luca Marco Matteo Giulia Francesca Sara Chiara Alessandro Andrea Davide Martina Elisa Paolo Federico Valentina Simone Giorgia Stefano Elena Roberto", "Rossi Russo Ferrari Esposito Bianchi Romano Colombo Ricci Marino Greco Bruno Gallo Conti De_Luca Costa Giordano"),
 "PT": ("Joao Tiago Miguel Rui Pedro Ana Beatriz Ines Marta Sofia Diogo Rita Goncalo Catarina Andre Filipa Bruno Mariana Hugo Carla", "Silva Santos Ferreira Pereira Oliveira Costa Rodrigues Martins Jesus Sousa Fernandes Goncalves Gomes Lopes Marques Alves"),
 "DK": ("Mads Mikkel Frederik Emil Oliver Freja Ida Emma Sofie Laura Rasmus Jonas Anders Camilla Signe Henrik Lone Soren Maja Kasper", "Nielsen Jensen Hansen Pedersen Andersen Christensen Larsen Sorensen Rasmussen Jorgensen Petersen Madsen Kristensen Olsen Thomsen"),
 "SE": ("Erik Lars Oscar Elias Hugo Alva Maja Ella Saga Wilma Johan Anders Karin Linnea Nils Emil Sara Gustav Astrid Viktor", "Andersson Johansson Karlsson Nilsson Eriksson Larsson Olsson Persson Svensson Gustafsson Pettersson Jonsson Jansson Hansson Bengtsson"),
 "PL": ("Jakub Kacper Szymon Filip Mateusz Zuzanna Julia Maja Hanna Lena Piotr Marcin Agnieszka Katarzyna Tomasz Michal Ewa Anna Pawel Magda", "Nowak Kowalski Wisniewski Wojcik Kowalczyk Kaminski Lewandowski Zielinski Szymanski Wozniak Dabrowski Kozlowski Jankowski Mazur Krawczyk"),
 "GR": ("Giorgos Dimitris Nikos Kostas Yannis Maria Eleni Katerina Sofia Anna Panagiotis Christos Vasilis Despina Ioanna Thanos Stavros Eirini Alexandros Georgia", "Papadopoulos Georgiou Dimitriou Nikolaou Vlachos Pappas Karagiannis Makris Antoniou Oikonomou Konstantinou Ioannou Vasileiou Angelopoulos Papadakis"),
 "IE": ("Conor Sean Cian Oisin Darragh Aoife Niamh Ciara Saoirse Roisin Padraig Liam Eoin Siobhan Clodagh Declan Brendan Sinead Fionn Orla", "Murphy Kelly OSullivan Walsh Smith OBrien Byrne Ryan OConnor ONeill Doyle McCarthy Gallagher Doherty Kennedy"),
}
NAMES["AT"] = NAMES["DE"]; NAMES["CH"] = NAMES["DE"]
NAMES = {k: (v[0].split(), [x.replace("_", " ") for x in v[1].split()]) for k, v in NAMES.items()}
def person(cc):
    if random.random() < .25: cc = random.choice(list(NAMES))
    f, l = NAMES[cc]; return random.choice(f), random.choice(l)
CIDX = {"CH": 1.35, "DK": 1.25, "NL": 1.10, "DE": 1.08, "FR": 1.05, "SE": 1.12, "AT": 1.05, "IE": 1.10, "IT": .95, "ES": .85, "PT": .75, "GR": .70, "PL": .60}
CAP = {"Pilot": 85, "Cabin Crew": 90, "Ground Staff": 150, "Maintenance Engineer": 140, "Operations Coordinator": 150}
DEPT = {"Pilot": "Flight Operations", "Cabin Crew": "Cabin Services", "Ground Staff": "Ground Operations", "Maintenance Engineer": "Technical / MRO", "Operations Coordinator": "Operations Control"}
NORTH = {"AMS", "FRA", "MUC", "CDG", "VIE", "ZRH", "CPH", "ARN", "WAW", "DUB"}
GSUB = [("Ramp Agent", 26, "GC_RAMP"), ("Baggage Handler", 20, "GC_BAGGAGE"), ("Check-in Agent", 14, "GC_CHECKIN"), ("Gate Agent", 10, "GC_GATE"),
        ("Load Controller", 3, "GC_LOADCONTROL"), ("Pushback Driver", 5, "GC_PUSHBACK"), ("De-icing Operator", 3, "GC_DEICING"), ("Fueler", 4, "GC_FUELING"),
        ("PRM Assistant", 7, "GC_PRM"), ("Aircraft Cleaner", 8, "GC_CLEANING")]
MSUB = [("B1 Engineer", 26), ("B2 Engineer", 12), ("Base Maintenance Certifier", 10), ("Technician", 52)]
OSUB = [("Duty Manager", 10, "OC_DUTYMGR"), ("Crew Controller", 24, "OC_CREWCTRL"), ("Flight Dispatcher", 24, "OC_DISPATCH"),
        ("Maintenance Controller", 14, "OC_MXCTRL"), ("Ground Ops Coordinator", 20, "OC_DUTYMGR"), ("Network Controller", 8, "OC_NETWORK")]
COST = {"Captain": 135, "First Officer": 80, "Purser": 38, "Cabin Attendant": 28, "Ramp Agent": 24, "Baggage Handler": 22, "Check-in Agent": 23, "Gate Agent": 24,
        "Load Controller": 33, "Pushback Driver": 25, "De-icing Operator": 26, "Fueler": 27, "PRM Assistant": 22, "Aircraft Cleaner": 20, "B1 Engineer": 46,
        "B2 Engineer": 48, "Base Maintenance Certifier": 55, "Technician": 34, "Duty Manager": 58, "Crew Controller": 46, "Flight Dispatcher": 52,
        "Maintenance Controller": 50, "Ground Ops Coordinator": 42, "Network Controller": 54}
emps = []
def tri(a, b, m): return date(int(random.triangular(a, b, m)), random.randint(1, 12), random.randint(1, 28))
def mk(role, sub, hub, hire, fleet=None, fams=None, body=None, tag=None):
    fn_, ln_ = person(HUB_CC[hub]); ft = random.random() < .88; fte = 1.0 if ft else random.choice([.6, .7, .8])
    yrs = (TODAY - hire).days / 365
    cost = COST[sub] * CIDX[HUB_CC[hub]] * random.uniform(.92, 1.08) * (1 + min(yrs, 25) * .008)
    emps.append(dict(first_name=fn_, last_name=ln_, role=role, sub_role=sub, department=DEPT[role], home_hub=hub, employment_type="EMPLOYEE",
                     contract_type="FULL_TIME" if ft else "PART_TIME", fte=fte, hire_date=hire.isoformat(), primary_fleet=fleet,
                     shift_pattern="ROSTERED" if role in ("Pilot", "Cabin Crew") else rc(["EARLY_5_2", "LATE_5_2", "NIGHT_4_3", "DAY_5_2", "ROTATING_4_4"], [28, 28, 14, 20, 10]),
                     hourly_cost_eur=round(cost, 2), monthly_capacity_hours=round(CAP[role] * fte, 1), _fams=fams or [], _body=body or [], _tag=tag))
for (hub, fam), n in pil_cells.items():
    for _ in range(n):
        cpt = random.random() < .42; fams = [fam]
        for (a, b, p) in (("A220", "A320FAM", .15), ("A320FAM", "A220", .08), ("E2", "A220", .05), ("A330", "A350", .20), ("A350", "A330", .10)):
            if fam == a and random.random() < p: fams.append(b)
        mk("Pilot", "Captain" if cpt else "First Officer", hub, tri(1996, 2019, 2012) if cpt else tri(2008, 2026, 2020), fam, fams)
for (hub, body), n in cab_cells.items():
    for _ in range(n):
        pur = random.random() < .18; bodies = [body]
        if body == "wide" and random.random() < .4: bodies.append("narrow")
        if body == "narrow" and random.random() < .08: bodies.append("wide")
        mk("Cabin Crew", "Purser" if pur else "Cabin Attendant", hub, tri(2000, 2020, 2010) if pur else tri(2005, 2026, 2019), "WIDE" if body == "wide" else "NARROW", body=bodies)
for hub, n in gnd_cells.items():
    sub = [(s, w, k) for s, w, k in GSUB if not (s == "De-icing Operator" and hub not in NORTH)]
    for _ in range(n):
        s = rc(sub, [x[1] for x in sub]); mk("Ground Staff", s[0], hub, tri(2000, 2026, 2020), tag=s[2])
for hub, n in mx_cells.items():
    fw = tails_fam_at[hub]; fl = list(fw) or FAMS
    for _ in range(n):
        s = rc([x[0] for x in MSUB], [x[1] for x in MSUB]); k = random.choice([1, 2, 2, 3]); pf = rc(fl, [fw.get(x, 1) for x in fl]); fams = [pf]
        for _ in range(k - 1):
            x = rc(fl, [fw.get(y, 1) for y in fl])
            if x not in fams: fams.append(x)
        mk("Maintenance Engineer", s, hub, tri(1998, 2026, 2016), pf if s != "Technician" else None, fams if s != "Technician" or random.random() < .5 else [])
for hub, n in ops_cells.items():
    for _ in range(n):
        s = rc(OSUB, [x[1] for x in OSUB]); mk("Operations Coordinator", s[0], hub, tri(1999, 2026, 2015), tag=s[2])
random.shuffle(emps)
for i, e in enumerate(emps): e["employee_id"] = f"E{i+1:06d}"
EM = {e["employee_id"]: e for e in emps}
print("employees:", len(emps))

# ----- employee skills
ES = []; EXP = defaultdict(dict)
def give(e, sid, level=None):
    mths = SKD[sid]["validity_months"]
    if mths:
        r = random.random()
        if r < .015: exp = TODAY - timedelta(days=random.randint(1, 120))
        elif r < .075: exp = TODAY + timedelta(days=random.randint(0, 60))
        else: exp = TODAY + timedelta(days=random.randint(61, mths * 30))
        obt = min(exp - timedelta(days=mths * 30 - random.randint(0, 20)), TODAY - timedelta(days=1))   # cannot be obtained in the future
        stt = "EXPIRED" if exp < TODAY else ("EXPIRING_SOON" if exp <= TODAY + timedelta(days=60) else "VALID")
        EXP[e["employee_id"]][sid] = exp; ex = exp.isoformat()
    else:
        obt = max(date.fromisoformat(e["hire_date"]), date(2000, 1, 1)) + timedelta(days=random.randint(0, 900)); obt = min(obt, TODAY - timedelta(days=30))
        stt = "VALID"; ex = None; EXP[e["employee_id"]][sid] = date.max
    ES.append((e["employee_id"], sid, level, obt.isoformat(), ex, stt))
LOCAL = {"NL": ["NL"], "DE": ["DE"], "FR": ["FR"], "ES": ["ES"], "IT": ["IT"], "PT": ["PT"], "AT": ["DE"], "CH": ["DE", "FR"], "DK": ["DA"], "SE": ["SV"], "PL": ["PL"], "GR": ["EL"], "IE": []}
XTRA = {"Pilot": .6, "Cabin Crew": 1.3, "Ground Staff": .7, "Maintenance Engineer": .4, "Operations Coordinator": .9}
for e in emps:
    r = e["role"]; langs = {"EN": rc(["C1", "C2"], [3, 1]) if r in ("Pilot", "Cabin Crew") else rc(["B1", "B2", "C1"], [3, 4, 2])}
    for l in LOCAL[HUB_CC[e["home_hub"]]][:random.choice([1, 2])]: langs[l] = "C2"
    for _ in range(int(XTRA[r]) + (random.random() < XTRA[r] % 1)):
        l = random.choice(list(LANGS)); langs.setdefault(l, random.choice(["A2", "B1", "B2", "C1"]))
    for l, lv in langs.items(): give(e, f"LANG_{l}", lv)
    give(e, "SC_AIRPORT_ID")
    if r != "Maintenance Engineer" or random.random() < .9: give(e, "SC_AVSEC")
    if r == "Pilot":
        for f in e["_fams"]: give(e, FAM_TR[f])
        if random.random() < .95: give(e, "PR_CAT3")
        if random.random() < .90: give(e, "PR_LVO")
        if any(f in ("A330", "A350", "B787") for f in e["_fams"]) and random.random() < .95: give(e, "PR_ETOPS")
        if e["sub_role"] == "Captain" and random.random() < .04: give(e, "PR_TRI")
        if e["sub_role"] == "Captain" and random.random() < .012: give(e, "PR_TRE")
        if random.random() < .6: give(e, "SC_DG")
    elif r == "Cabin Crew":
        for b in e["_body"]: give(e, "CQ_WIDE" if b == "wide" else "CQ_NARROW")
        give(e, "CC_SEP")
        if random.random() < .95: give(e, "CC_FIRSTAID")
        if e["sub_role"] == "Purser": give(e, "CC_PURSER")
        if random.random() < .3: give(e, "SC_DG")
    elif r == "Ground Staff":
        give(e, e["_tag"]); give(e, "SC_ENHANCED") if random.random() < .5 else None
        if e["sub_role"] in ("Load Controller", "Fueler") or random.random() < .25: give(e, "SC_DG")
        if e["sub_role"] != "PRM Assistant" and random.random() < .2: give(e, "GC_PRM")
    elif r == "Maintenance Engineer":
        s = e["sub_role"]
        give(e, {"B1 Engineer": "MC_B1", "B2 Engineer": "MC_B2", "Base Maintenance Certifier": "MC_C", "Technician": "MC_TECH"}[s])
        if s == "Base Maintenance Certifier": give(e, "MC_B1")
        for f in e["_fams"]: give(e, FAM_MT[f])
        if s == "Technician" and random.random() < .25: give(e, "MC_NDT")
        if random.random() < .08: give(e, "MC_COMPOSITE")
        if random.random() < .3: give(e, "SC_ENHANCED")
    else:
        give(e, e["_tag"]); give(e, "SC_ENHANCED")
T["employee_skills"] = [dict(employee_id=a, skill_id=b, level=c, obtained_date=d_, expiry_date=e_, status=f_) for a, b, c, d_, e_, f_ in ES]
print("employee skills:", len(ES))

# =====================================================================  AVAILABILITY (vacation, sickness, other)
AV = []; ABS = defaultdict(list)   # ABS: employee -> [(start_ord, end_ord)]  (approved/active only)
def add_av(eid, typ, s, e, status, src="HR_SYSTEM", sess=None, count=True):
    AV.append(dict(event_id=f"AV{len(AV)+1:06d}", employee_id=eid, event_type=typ, start_date=s.isoformat(), end_date=e.isoformat(), days=(e - s).days + 1,
                   status=status, source_system=src, training_session_id=sess))
    if count and status in ("APPROVED", "ACTIVE", "RECORDED", "ENROLLED"): ABS[eid].append((s.toordinal(), e.toordinal()))
def overlap(eid, s, e): return any(not (b < s.toordinal() or a > e.toordinal()) for a, b in ABS[eid])
vd = [date(2026, 10, 10) + timedelta(days=i) for i in range((date(2027, 10, 15) - date(2026, 10, 10)).days)]
def vw(d):
    if date(2027, 7, 1) <= d <= date(2027, 8, 31): return 3.2
    if date(2026, 12, 19) <= d <= date(2027, 1, 3): return 2.2
    if date(2027, 3, 26) <= d <= date(2027, 4, 11): return 1.8
    if date(2026, 10, 17) <= d <= date(2026, 11, 1): return 1.8
    if date(2027, 2, 13) <= d <= date(2027, 2, 28): return 1.3
    return 1.0
cw = []; acc = 0
for d in vd: acc += vw(d); cw.append(acc)
for e in emps:
    for _ in range(rc([1, 2, 3, 4], [15, 50, 30, 5])):
        for _try in range(5):
            s = random.choices(vd, cum_weights=cw)[0]; ln = rc([4, 5, 7, 9, 10, 14, 16, 21], [10, 12, 25, 10, 10, 22, 5, 6]); en = s + timedelta(days=ln - 1)
            if not overlap(e["employee_id"], s, en): break
        else: continue
        ahead = (s - TODAY).days; pa = .93 if ahead <= 90 else (.60 if ahead <= 240 else .45)
        add_av(e["employee_id"], "VACATION", s, en, "APPROVED" if random.random() < pa else "PENDING", count=True)
        if AV[-1]["status"] == "PENDING": ABS[e["employee_id"]].pop() if False else None
for e in emps:
    eid = e["employee_id"]
    if random.random() < .14:
        s = rdate(date(2026, 9, 1), TODAY - timedelta(days=8)); add_av(eid, "SICK", s, s + timedelta(days=random.randint(1, 7)), "RECORDED")
    r = random.random()
    if r < .032 and not overlap(eid, TODAY, TODAY + timedelta(days=3)): add_av(eid, "SICK", TODAY - timedelta(days=random.randint(0, 5)), TODAY + timedelta(days=random.randint(1, 10)), "ACTIVE")
    elif r < .040: add_av(eid, "SICK", TODAY - timedelta(days=random.randint(5, 60)), TODAY + timedelta(days=random.randint(30, 120)), "ACTIVE")
    elif r < .049 and not overlap(eid, date(2026, 11, 1), date(2027, 6, 30)):
        s = rdate(date(2026, 10, 1), date(2027, 5, 1)); add_av(eid, "PARENTAL_LEAVE", s, s + timedelta(days=random.randint(90, 240)), "APPROVED")
    elif r < .060:
        s = rdate(date(2026, 11, 1), date(2027, 8, 1))
        if not overlap(eid, s, s + timedelta(days=6)): add_av(eid, "UNPAID_LEAVE", s, s + timedelta(days=random.randint(3, 20)), "APPROVED")
# recompute ABS strictly from approved/active (pending vacations must not block)
ABS = defaultdict(list)
for a in AV:
    if a["status"] in ("APPROVED", "ACTIVE", "RECORDED"): ABS[a["employee_id"]].append((date.fromisoformat(a["start_date"]).toordinal(), date.fromisoformat(a["end_date"]).toordinal()))

# =====================================================================  TRAINING
MONTHS = [(2026, 10)] + [(2026, 11), (2026, 12)] + [(2027, m) for m in range(1, 11)]
SESS = []; SBK = defaultdict(list); SIM_HUBS = ["AMS", "FRA", "MUC", "MAD", "CDG"]
def nearest_sim(h): return min(SIM_HUBS, key=lambda s: hav(h, s))
def add_sessions(code, name, group, skill, hub, per_month, days, cap, loc, fam=None, instr=0, instr_skill=None):
    for (y, m) in MONTHS:
        n = per_month if (y, m) != (2026, 10) else max(1, per_month // 4)
        for _ in range(n):
            for _t in range(60):
                dd = date(y, m, random.randint(1, 28))
                if dd >= TODAY + timedelta(days=2) and dd.isoweekday() < 6 and dd <= PLAN_END: break
            else: continue
            s = dict(session_id=f"TS{len(SESS)+1:05d}", course_code=code, course_name=name, target_role_group=group, skill_id_granted=skill, target_fleet_family=fam, hub=hub,
                     location_type=loc, start_date=dd.isoformat(), end_date=(dd + timedelta(days=days - 1)).isoformat(), capacity=cap, enrolled=0,
                     instructors_required=instr, instructor_skill_id=instr_skill, status="PLANNED", _s=dd, _e=dd + timedelta(days=days - 1))
            SESS.append(s); SBK[(hub, code, fam)].append(s)
cnt_sk = defaultdict(int)
for (eid, sid, *_r) in ES:
    cnt_sk[(EM[eid]["home_hub"], sid)] += 1
sim_cnt = defaultdict(int)
for e in emps:
    if e["role"] == "Pilot":
        for f in e["_fams"]: sim_cnt[(nearest_sim(e["home_hub"]), f)] += 1
for (sh, f), n in sim_cnt.items():
    add_sessions("SIM_PC", f"Simulator proficiency check {f}", "Pilot", FAM_TR[f], sh, max(1, math.ceil(1.5 * n / 12 / 8)), 1, 8, "SIMULATOR", f, 1, "PR_TRI")
COURSES = {"SEP": ("Safety & Emergency Procedures recurrent", "Cabin Crew", "CC_SEP", 1, 24), "FIRSTAID": ("Cabin first aid", "Cabin Crew", "CC_FIRSTAID", 1, 20),
           "AVSEC": ("Aviation security awareness", "All", "SC_AVSEC", 1, 30), "DG": ("Dangerous goods", "Multiple", "SC_DG", 2, 20),
           "DEICING": ("De-icing operator refresher", "Ground Staff", "GC_DEICING", 2, 16), "PRM": ("PRM assistance", "Ground Staff", "GC_PRM", 1, 20),
           "LOADCTRL": ("Load control refresher", "Ground Staff", "GC_LOADCONTROL", 3, 12)}
for code, (nm, grp, skill, days, cap) in COURSES.items():
    mths = SKD[skill]["validity_months"]
    for h in HUB_CODES:
        n = cnt_sk.get((h, skill), 0)
        if n: add_sessions(code, nm, grp, skill, h, max(1, math.ceil(1.5 * n / mths / cap)), days, cap, "CLASSROOM")
# conversion / development courses
for _ in range(6): add_sessions("TR_CONV", "Pilot type rating conversion course", "Pilot", None, random.choice(SIM_HUBS), 1, 20, 8, "SIMULATOR", None, 2, "PR_TRI")
for h in ("AMS", "FRA", "MUC", "CDG", "MAD", "LIS"): add_sessions("MX_TYPE", "Engineer type course (B1/B2)", "Maintenance Engineer", None, h, 1, 10, 14, "CLASSROOM")
for h in HUB_CODES: add_sessions("PURSER", "Purser development course", "Cabin Crew", "CC_PURSER", h, 1, 8, 16, "CLASSROOM")
for k in SBK: SBK[k].sort(key=lambda s: s["_s"])
ENR = []
def enroll(eid, key, earliest, latest, reason):
    for s in SBK.get(key, []):
        if s["_s"] < earliest: continue
        if s["_s"] > latest: break
        if s["enrolled"] >= s["capacity"] or overlap(eid, s["_s"], s["_e"]): continue
        s["enrolled"] += 1; ENR.append(dict(enrollment_id=f"EN{len(ENR)+1:06d}", session_id=s["session_id"], employee_id=eid, status="ENROLLED", reason=reason))
        add_av(eid, "TRAINING", s["_s"], s["_e"], "ENROLLED", "TRAINING_SYSTEM", s["session_id"]); return True
    return False
SK2COURSE = {sid: s["renewal_course_code"] for sid, s in SKD.items() if s["renewal_course_code"] and s["renewal_course_code"] != "SIM_PC"}
horizon = TODAY + timedelta(days=365); unenr = 0
for e in emps:
    eid = e["employee_id"]; h = e["home_hub"]
    todo = []
    if e["role"] == "Pilot":
        for f in e["_fams"]:
            if FAM_TR[f] in EXP[eid]: todo.append((FAM_TR[f], (nearest_sim(h), "SIM_PC", f)))
    for sid, exp in EXP[eid].items():
        c = SK2COURSE.get(sid)
        if c: todo.append((sid, (h, c, None)))
    for sid, key in todo:
        exp = EXP[eid][sid]
        if exp > horizon: continue
        if exp < TODAY + timedelta(days=14): lo, hi = TODAY + timedelta(days=2), TODAY + timedelta(days=75)
        else: lo, hi = max(TODAY + timedelta(days=2), exp - timedelta(days=75)), exp - timedelta(days=1)
        if not enroll(eid, key, lo, hi, "RENEWAL_DUE"): unenr += 1
for e in random.sample([e for e in emps if e["role"] == "Pilot"], 120):
    enroll(e["employee_id"], (nearest_sim(e["home_hub"]), "TR_CONV", None) if False else None, date(1,1,1), date(1,1,1), "") if False else None
print("sessions:", len(SESS), " enrollments:", len(ENR), " renewals without a session:", unenr)
T["training_sessions"] = [{k: v for k, v in s.items() if not k.startswith("_")} for s in SESS]
T["training_enrollments"] = ENR
T["availability_events"] = AV
ABS = defaultdict(list)
for a in AV:
    if a["status"] in ("APPROVED", "ACTIVE", "RECORDED", "ENROLLED"): ABS[a["employee_id"]].append((date.fromisoformat(a["start_date"]).toordinal(), date.fromisoformat(a["end_date"]).toordinal()))
def absent(eid, o): return any(a <= o <= b for a, b in ABS.get(eid, ()))
cur = {}
for a in AV:
    if a["status"] in ("APPROVED", "ACTIVE", "ENROLLED") and a["start_date"] <= TODAY.isoformat() <= a["end_date"]:
        cur[a["employee_id"]] = {"VACATION": "ON_LEAVE", "SICK": "SICK", "PARENTAL_LEAVE": "ON_LEAVE", "UNPAID_LEAVE": "ON_LEAVE", "TRAINING": "IN_TRAINING"}[a["event_type"]]
for e in emps: e["current_status"] = cur.get(e["employee_id"], "ACTIVE")
T["employees"] = [{k: v for k, v in e.items() if not k.startswith("_")} for e in emps]

# =====================================================================  CREW ASSIGNMENTS TO FLIGHTS (first 14 days)
pools = defaultdict(list)
for e in emps:
    if e["role"] == "Pilot":
        for f in e["_fams"]: pools[(e["home_hub"], f, "CPT" if e["sub_role"] == "Captain" else "FO")].append(e)
    elif e["role"] == "Cabin Crew":
        for b in e["_body"]: pools[(e["home_hub"], b, "PUR" if e["sub_role"] == "Purser" else "CA")].append(e)
st = {}   # employee -> dict(last_end, duty_start, duty_block, legs, total)
def can(e, f, tr_skills):
    eid = e["employee_id"]; o1 = f["_date"].toordinal(); o2 = (EPOCH + timedelta(minutes=f["_am"])).date().toordinal()
    if absent(eid, o1) or absent(eid, o2): return False
    ex = EXP[eid]
    for s in tr_skills:
        if ex.get(s, date.min) < f["_date"]: return False
    s_ = st.get(eid)
    if s_ and (f["_dm"] < s_["last_end"] + 45): return False
    if s_ and s_["total"] + f["block_minutes"] > e["monthly_capacity_hours"] * 60 * ROSTER_DAYS / 30 * 1.15: return False
    if s_ and s_["duty_start"] is not None and f["_dm"] <= s_["last_end"] + 300 and f["_am"] - s_["duty_start"] <= 13 * 60 and s_["duty_block"] + f["block_minutes"] <= 600 and s_["legs"] < 4: return True
    if s_ and f["_dm"] < s_["last_end"] + 720: return False
    return True
def commit(e, f):
    eid = e["employee_id"]; s_ = st.get(eid)
    if s_ and s_["duty_start"] is not None and f["_dm"] <= s_["last_end"] + 300 and f["_am"] - s_["duty_start"] <= 780 and s_["duty_block"] + f["block_minutes"] <= 600 and s_["legs"] < 4:
        s_["duty_block"] += f["block_minutes"]; s_["legs"] += 1
    else:
        s_ = st[eid] = dict(last_end=0, duty_start=f["_dm"] - 60, duty_block=f["block_minutes"], legs=1, total=(s_ or {}).get("total", 0))
    s_["last_end"] = f["_am"]; s_["total"] += f["block_minutes"]
FA = []; pair_crew = {}
roster_end = TODAY + timedelta(days=ROSTER_DAYS - 1)
for f in inst:
    if f["_date"] > roster_end or f["status"] == "CANCELLED": continue
    pairkey = (f["rotation_pair_id"], f["operating_date"]); fam, body, hub = f["_fam"], f["_body"], f["crew_base_hub"]
    np_ = ppf(f["block_minutes"]); ncab = ACT[f["aircraft_type"]]["cabin_min"]
    slots = [("Pilot", "Captain", (hub, fam, "CPT"), [FAM_TR[fam]]), ] + [("Pilot", "First Officer", (hub, fam, "FO"), [FAM_TR[fam]])] * (np_ - 1) \
          + [("Cabin Crew", "Purser", (hub, body, "PUR"), ["CC_SEP", "CQ_WIDE" if body == "wide" else "CQ_NARROW"])] \
          + [("Cabin Crew", "Cabin Attendant", (hub, body, "CA"), ["CC_SEP", "CQ_WIDE" if body == "wide" else "CQ_NARROW"])] * (ncab - 1)
    prev = pair_crew.get(pairkey, []); used = set(); crew = []
    pub = "PUBLISHED" if f["_date"] <= TODAY + timedelta(days=6) else "DRAFT"
    for i, (role, slot, key, sks) in enumerate(slots):
        chosen = None
        for (pslot, pe) in prev:
            if pslot == slot and pe["employee_id"] not in used and (pe["role"], ) and can(pe, f, sks) and pe["employee_id"] not in {c[1]["employee_id"] for c in crew if False}:
                chosen = pe; break
        if chosen is None:
            pl = pools.get(key, [])
            if pl:
                o = random.randrange(len(pl))
                for j in range(len(pl)):
                    cnd = pl[(o + j) % len(pl)]
                    if cnd["employee_id"] in used: continue
                    if can(cnd, f, sks): chosen = cnd; break
        if chosen is not None:
            used.add(chosen["employee_id"]); commit(chosen, f); crew.append((slot, chosen))
            FA.append((f["flight_id"], chosen["employee_id"], role, slot, "ASSIGNED", pub))
        else:
            FA.append((f["flight_id"], None, role, slot, "UNFILLED", pub))
    pair_crew[pairkey] = crew
T["flight_crew_assignments"] = [dict(assignment_id=f"FA{i+1:06d}", flight_id=a, employee_id=b, role=c, slot=d_, status=e_, roster_status=f_) for i, (a, b, c, d_, e_, f_) in enumerate(FA)]
print("crew slots:", len(FA), "unfilled:", sum(1 for x in FA if x[4] == "UNFILLED"))
T["flights"] = [{k: v for k, v in f.items() if not k.startswith("_")} for f in inst]

# =====================================================================  MAINTENANCE REQUIREMENTS & ASSIGNMENTS
MXSPLIT = {"C_CHECK": (.28, .12, .03, .57), "A_CHECK": (.30, .10, .06, .54), "UNSCHEDULED_DEFECT": (.45, .20, .05, .30), "DEFERRED_DEFECT": (.50, .15, .05, .30)}
REQ = []; ACTREQ = defaultdict(list)
for x in acts:
    if x["status"] == "COMPLETED": continue
    fam = AC[x["tail_number"]]["family"]; days = max(1, math.ceil((x["_e"] - x["_s"]).total_seconds() / 86400))
    for (sub, lic, frac) in zip(("B1 Engineer", "B2 Engineer", "Base Maintenance Certifier", "Technician"), ("MC_B1", "MC_B2", "MC_C", "MC_TECH"), MXSPLIT[x["activity_type"]]):
        if x["activity_type"] != "C_CHECK" and sub == "Base Maintenance Certifier": sub, lic = "B1 Engineer", "MC_B1"
        if x["activity_type"] == "C_CHECK" and sub == "Base Maintenance Certifier" : pass
        hc = min(40, max(1, math.ceil(x["estimated_man_hours"] * frac / (days * 8))))
        r = dict(requirement_id=f"RQ{len(REQ)+1:06d}", activity_id=x["activity_id"], role="Maintenance Engineer", sub_role=sub, required_license_skill=lic,
                 required_type_skill=FAM_MT[fam] if sub != "Technician" else None, headcount=hc, hours_each=round(min(x["estimated_man_hours"] * frac / hc, days * 8), 1))
        REQ.append(r); ACTREQ[x["activity_id"]].append(r)
T["maintenance_requirements"] = REQ
eng = defaultdict(list)
for e in emps:
    if e["role"] == "Maintenance Engineer": eng[(e["home_hub"], e["sub_role"])].append(e)
busy = defaultdict(list); MA = []
horizon_a = datetime.combine(TODAY + timedelta(days=28), datetime.min.time())
for x in acts:
    if x["status"] == "COMPLETED" or x["_s"] > horizon_a: continue
    s0, e0 = x["_s"].date(), x["_e"].date()
    for r in ACTREQ[x["activity_id"]]:
        pl = eng[(x["hub"], r["sub_role"])]; got = 0
        if pl:
            o = random.randrange(len(pl))
            for j in range(len(pl)):
                if got >= r["headcount"]: break
                c = pl[(o + j) % len(pl)]; cid = c["employee_id"]; ex = EXP[cid]
                if ex.get(r["required_license_skill"], date.min) < s0 or (r["required_type_skill"] and r["required_type_skill"] not in ex): continue
                if overlap(cid, s0, e0) or any(not (b < s0.toordinal() or a > e0.toordinal()) for a, b in busy[cid]): continue
                busy[cid].append((s0.toordinal(), e0.toordinal())); got += 1
                MA.append(dict(assignment_id=f"MA{len(MA)+1:06d}", activity_id=x["activity_id"], requirement_id=r["requirement_id"], employee_id=cid, status="ASSIGNED"))
        for _ in range(r["headcount"] - got):
            MA.append(dict(assignment_id=f"MA{len(MA)+1:06d}", activity_id=x["activity_id"], requirement_id=r["requirement_id"], employee_id=None, status="UNFILLED"))
T["maintenance_assignments"] = MA
print("mx slots:", len(MA), "unfilled:", sum(1 for m in MA if m["status"] == "UNFILLED"))
T["maintenance_activities"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in acts]

# =====================================================================  CONTRACTORS
AGENCIES = ["AeroTemps", "SkyStaff Partners", "Ground Force Europe", "TechAvia Contracting", "CrewBridge", "Nordic Aviation Resourcing", "Iberia Aero Services", "Alpine Workforce"]
con = []
for _ in range(1900):
    h = rc(HUB_CODES, [gnd_w[x] for x in HUB_CODES]); r = rc(["Ground Staff", "Maintenance Engineer", "Cabin Crew", "Operations Coordinator"], [58, 24, 14, 4])
    if r == "Ground Staff": s = rc(GSUB, [x[1] for x in GSUB]); sub, skills = s[0], [s[2], "SC_AIRPORT_ID"]; rate = 190
    elif r == "Maintenance Engineer": sub = rc(["B1 Engineer", "B2 Engineer", "Technician"], [35, 15, 50]); skills = [{"B1 Engineer": "MC_B1", "B2 Engineer": "MC_B2", "Technician": "MC_TECH"}[sub], FAM_MT[random.choice(FAMS)], "SC_AIRPORT_ID"] if sub != "Technician" else ["MC_TECH", "SC_AIRPORT_ID"]; rate = 420 if sub != "Technician" else 290
    elif r == "Cabin Crew": sub = "Cabin Attendant"; skills = ["CQ_NARROW", "CC_SEP", "SC_AIRPORT_ID"]; rate = 230
    else: sub = "Ground Ops Coordinator"; skills = ["OC_DUTYMGR", "SC_ENHANCED"]; rate = 380
    seasonal = r == "Cabin Crew" and random.random() < .6
    s0 = date(2027, 4, 1) if seasonal else rdate(date(2026, 1, 1), date(2026, 10, 20)); e0 = date(2027, 10, 31) if seasonal else s0 + timedelta(days=random.randint(90, 540))
    con.append(dict(contractor_id=f"C{len(con)+1:05d}", agency=random.choice(AGENCIES), role=r, sub_role=sub, home_hub=h, day_rate_eur=round(rate * CIDX[HUB_CC[h]] * random.uniform(.9, 1.1)),
                    contract_start=s0.isoformat(), contract_end=e0.isoformat(), status="UPCOMING" if s0 > TODAY else ("ACTIVE" if e0 >= TODAY else "ENDED"), skills=skills))
T["contractors"] = [{**c, "skills": "|".join(c["skills"])} for c in con]

# =====================================================================  CALENDAR, EVENTS, NEW ROUTES, SCENARIOS, RULES
def iata_season(d):
    s, w = last_sunday(d.year, 3), last_sunday(d.year, 10)
    if d < s: return f"W{(d.year-1)%100}/{d.year%100}"
    if d < w: return f"S{d.year%100}"
    return f"W{d.year%100}/{(d.year+1)%100}"
SEAS = {1: .85, 2: .85, 3: .93, 4: 1.0, 5: 1.05, 6: 1.12, 7: 1.20, 8: 1.22, 9: 1.08, 10: 1.0, 11: .88, 12: .93}
HOLNAMES = {(1, 1): "New Year's Day", (5, 1): "Labour Day", (12, 25): "Christmas Day", (12, 26): "Boxing Day / St Stephen's Day"}
cal = []; d = date(2024, 1, 1)
while d <= date(2027, 12, 31):
    pk = (date(d.year, 7, 1) <= d <= date(d.year, 8, 31)) or d >= date(d.year, 12, 19) or d <= date(d.year, 1, 4)
    cal.append(dict(date=d.isoformat(), year=d.year, quarter=(d.month - 1) // 3 + 1, month=d.month, month_name=d.strftime("%B"), iso_week=d.isocalendar()[1],
                    day_of_week=d.isoweekday(), day_name=d.strftime("%A"), is_weekend=int(d.isoweekday() >= 6), iata_season=iata_season(d),
                    is_peak_travel_period=int(pk), seasonal_demand_index=SEAS[d.month], public_holiday=HOLNAMES.get((d.month, d.day))))
    d += timedelta(days=1)
T["calendar"] = cal
EV = [("Lisbon Tech Summit (illustrative)", "LIS", "2026-11-09", "2026-11-12", 45000, 12), ("Munich Christmas markets surge", "MUC", "2026-11-26", "2026-12-23", 80000, 18),
      ("Vienna Christmas markets surge", "VIE", "2026-11-20", "2026-12-23", 40000, 8), ("Alpine ski season opening", "ZRH", "2026-12-12", "2027-01-10", 60000, 14),
      ("Winter school holidays Nordics", "ARN", "2027-02-13", "2027-02-28", 35000, 10), ("Barcelona mobile trade fair (illustrative)", "BCN", "2027-03-01", "2027-03-04", 60000, 16),
      ("Easter peak", "FCO", "2027-03-25", "2027-04-05", 120000, 30), ("Madrid marathon week (illustrative)", "MAD", "2027-04-22", "2027-04-26", 25000, 6),
      ("Dutch Grand Prix weekend (illustrative)", "AMS", "2027-08-27", "2027-08-29", 55000, 14), ("Athens summer island peak", "ATH", "2027-07-15", "2027-08-31", 220000, 40),
      ("Dublin rugby international (illustrative)", "DUB", "2027-02-04", "2027-02-07", 30000, 8), ("Copenhagen design week (illustrative)", "CPH", "2027-06-02", "2027-06-06", 20000, 5),
      ("Warsaw airshow (illustrative)", "WAW", "2027-09-04", "2027-09-05", 15000, 4), ("Paris trade fair season", "CDG", "2027-06-14", "2027-06-20", 90000, 22)]
T["special_events"] = [dict(event_id=f"EVT{i+1:03d}", name=n, hub=h, start_date=s, end_date=e, expected_additional_passengers=p, expected_additional_flights_per_day=fl,
                            ground_staff_uplift_pct=random.choice([5, 8, 10, 15]), notes="Synthetic event; all figures illustrative") for i, (n, h, s, e, p, fl) in enumerate(EV)]
NR = [("AMS", "NRT", "2027-03-28", 7, "B787-9", "APPROVED"), ("MUC", "BOS", "2027-03-28", 5, "A350-900", "APPROVED"), ("LIS", "GRU", "2027-05-03", 4, "A330-900", "APPROVED"),
      ("FRA", "DEL", "2027-06-01", 4, "A350-900", "PLANNED"), ("BCN", "TLV", "2027-03-28", 7, "A321neo", "APPROVED"), ("CPH", "KEF", "2027-04-26", 5, "A220-300", "PLANNED"),
      ("WAW", "LCA", "2027-05-01", 3, "A320neo", "PLANNED"), ("ZRH", "MIA", "2027-09-01", 4, "A350-900", "UNDER_REVIEW")]
nr_rows, nr_req = [], []
for i, (o, dd, ld, fr, typ, stt) in enumerate(NR):
    dist = hav(o, dd); sp = ACT[typ]; blk = int(dist / sp["speed"] * 60 + 32); rid = f"NR{i+1:03d}"
    nr_rows.append(dict(route_launch_id=rid, origin=o, destination=dd, launch_date=ld, frequency_per_week=fr, aircraft_type=typ, block_minutes=blk, distance_km=int(dist), status=stt,
                        expected_load_factor_ramp="0.65 -> 0.80 over 6 months"))
    hrs = fr * 4.33 * 2 * blk / 60
    for role, sub, n, sk_, lead in (("Pilot", "Captain", math.ceil(hrs * ppf(blk) / 2 * .5 / (85 * .75)), FAM_TR[sp["fam"]], 120), ("Pilot", "First Officer", math.ceil(hrs * (ppf(blk) - 1) / ((ppf(blk) - 1)) * .5 * (ppf(blk) - 1) / (85 * .75)), FAM_TR[sp["fam"]], 120),
                                   ("Cabin Crew", "Cabin Attendant", math.ceil(hrs * sp["cabin_min"] / (90 * .75)), "CQ_WIDE" if sp["body"] == "wide" else "CQ_NARROW", 60),
                                   ("Ground Staff", "Ramp Agent", math.ceil(fr * 2.2), "GC_RAMP", 30), ("Ground Staff", "Check-in Agent", math.ceil(fr * 1.6), "GC_CHECKIN", 30),
                                   ("Maintenance Engineer", "B1 Engineer", math.ceil(fr / 3), FAM_MT[sp["fam"]], 90)):
        nr_req.append(dict(route_launch_id=rid, role=role, sub_role=sub, headcount_required=n, required_skill_id=sk_, ready_by_date=(date.fromisoformat(ld) - timedelta(days=lead)).isoformat(),
                           location_hub=o))
T["new_route_launches"] = nr_rows; T["new_route_requirements"] = nr_req
T["candidate_hubs"] = [dict(candidate_id=f"CH{i+1}", airport=a, city=AP[a]["city"], country=AP[a]["country"], planned_open_date=od, year1_daily_departures=y1, year3_daily_departures=y3,
                            aircraft_to_base=ac, staff_relocating_share_pct=rl, line_maintenance_bays=bays, estimated_gates_required=gt, local_labour_cost_index=ci, setup_cost_eur_m=sc)
                       for i, (a, od, y1, y3, ac, rl, bays, gt, ci, sc) in enumerate([("BRU", "2027-10-31", 45, 90, 22, 30, 2, 18, 1.05, 85), ("MXP", "2028-03-26", 60, 130, 35, 25, 3, 26, .95, 120), ("PRG", "2027-10-31", 30, 70, 14, 35, 2, 14, .70, 55)])]
RULES = [("FTL-P-01", "Pilot", "Max flight duty period (basic)", 13, "hours", "per duty", "Simplified; loosely modelled on EASA ORO.FTL. Not legal advice."), ("FTL-P-02", "Pilot", "Max block time", 100, "hours", "rolling 28 days", "Simplified"),
         ("FTL-P-03", "Pilot", "Max block time", 900, "hours", "calendar year", "Simplified"), ("FTL-P-04", "Pilot", "Minimum rest between duties", 12, "hours", "per duty", "Simplified (home base)"),
         ("FTL-P-05", "Pilot", "Max consecutive duty days", 6, "days", "rolling", "Simplified"), ("FTL-P-06", "Pilot", "Max sectors per duty", 4, "sectors", "per duty", "Simplified"),
         ("FTL-C-01", "Cabin Crew", "Max duty period", 13, "hours", "per duty", "Simplified"), ("FTL-C-02", "Cabin Crew", "Minimum rest between duties", 10, "hours", "per duty", "Simplified"),
         ("FTL-C-03", "Cabin Crew", "Max flight time", 100, "hours", "rolling 28 days", "Simplified"), ("MX-01", "Maintenance Engineer", "Max working time", 10, "hours", "per day", "Simplified"),
         ("MX-02", "Maintenance Engineer", "Certifying staff must hold valid licence AND type endorsement for the aircraft family", None, None, "per task sign-off", "Compliance rule"),
         ("LIC-01", "Pilot", "Type rating must be valid (not expired) on the date of flight", None, None, "per flight", "Compliance rule"),
         ("SEC-01", "All", "Valid airport access ID required for airside work", None, None, "per shift", "Compliance rule"), ("GR-01", "Ground Staff", "De-icing operators need valid annual de-icing certificate", None, None, "per shift", "Compliance rule"),
         ("CC-01", "Cabin Crew", "Minimum cabin crew = 1 per 50 seats (see aircraft_types.min_cabin_crew); every flight needs a qualified Purser", None, None, "per flight", "Compliance rule")]
T["regulatory_rules"] = [dict(rule_id=a, applies_to_role=b, rule_name=c, limit_value=d_, unit=e_, window=f_, notes=g) for a, b, c, d_, e_, f_, g in RULES]
SR = []
for typ, sp in ACT.items():
    SR += [dict(aircraft_type=typ, phase="FLIGHT_DECK", role="Pilot", sub_role="Captain", headcount=1, duration_basis="block_time", fixed_hours=None, required_skill_id=sp["tr"]),
           dict(aircraft_type=typ, phase="FLIGHT_DECK", role="Pilot", sub_role="First Officer", headcount=1, duration_basis="block_time", fixed_hours=None, required_skill_id=sp["tr"]),
           dict(aircraft_type=typ, phase="FLIGHT_DECK", role="Pilot", sub_role="First Officer (relief, if block >= 8h)", headcount=1, duration_basis="block_time", fixed_hours=None, required_skill_id=sp["tr"]),
           dict(aircraft_type=typ, phase="CABIN", role="Cabin Crew", sub_role="Purser", headcount=1, duration_basis="block_time", fixed_hours=None, required_skill_id="CC_PURSER"),
           dict(aircraft_type=typ, phase="CABIN", role="Cabin Crew", sub_role="Cabin Attendant", headcount=sp["cabin_min"] - 1, duration_basis="block_time", fixed_hours=None, required_skill_id="CQ_WIDE" if sp["body"] == "wide" else "CQ_NARROW")]
    k = sp["seats"] / 180
    for sub, n, hrs, skl in (("Ramp Agent", 4, 1.25, "GC_RAMP"), ("Baggage Handler", 5, 1.5, "GC_BAGGAGE"), ("Pushback Driver", 1, .5, "GC_PUSHBACK"), ("Load Controller", 1, 1.0, "GC_LOADCONTROL"),
                             ("Gate Agent", 3, 1.5, "GC_GATE"), ("Check-in Agent", 5, 2.0, "GC_CHECKIN"), ("PRM Assistant", 1, 1.0, "GC_PRM"), ("Aircraft Cleaner", 4, 1.0, "GC_CLEANING"), ("Fueler", 1, .75, "GC_FUELING")):
        SR.append(dict(aircraft_type=typ, phase="TURNAROUND", role="Ground Staff", sub_role=sub, headcount=max(1, round(n * k)), duration_basis="fixed_hours", fixed_hours=hrs, required_skill_id=skl))
for i, r in enumerate(SR): r["requirement_id"] = f"SRV{i+1:04d}"
T["service_requirements"] = [{**{"requirement_id": r["requirement_id"]}, **{k: v for k, v in r.items() if k != "requirement_id"}} for r in SR]

# =====================================================================  NETWORK PLAN, KPI HISTORY, BUDGETS
HC = defaultdict(int); CAPT = defaultdict(float); CST = defaultdict(list)
for e in emps: HC[(e["home_hub"], e["role"])] += 1; CAPT[(e["home_hub"], e["role"])] += e["monthly_capacity_hours"]; CST[(e["home_hub"], e["role"])].append(e["hourly_cost_eur"])
ROLES = list(CAP); AVGSEAT = sum(a["seats"] for a in aircraft) / len(aircraft)
plan = []; m0 = (2026, 11); mm = []
y, m = 2026, 11
while (y, m) <= (2027, 12): mm.append((y, m)); m += 1; y, m = (y + 1, 1) if m == 13 else (y, m)
dim = lambda y, m: (date(y + (m == 12), m % 12 + 1, 1) - date(y, m, 1)).days
for (y, m) in mm:
    g = 1.04 ** ((date(y, m, 1) - date(2026, 10, 1)).days / 365)
    for h in HUB_CODES:
        fl = fl_touch[h] * dim(y, m) * SEAS[m] * g; pax = fl * AVGSEAT * SEAS_LF[m]
        plan.append(dict(month=f"{y}-{m:02d}", hub=h, planned_flights=int(fl), forecast_passengers_base=int(pax), forecast_passengers_low=int(pax * .93), forecast_passengers_high=int(pax * 1.08),
                         expected_load_factor=SEAS_LF[m], seasonal_index=SEAS[m], growth_index=round(g, 3)))
T["network_plan_monthly"] = plan
VAC = {1: .09, 2: .08, 3: .08, 4: .10, 5: .09, 6: .11, 7: .17, 8: .19, 9: .11, 10: .10, 11: .07, 12: .12}; SICKR = {1: .055, 2: .05, 3: .04, 4: .035, 5: .03, 6: .03, 7: .03, 8: .03, 9: .035, 10: .04, 11: .05, 12: .055}
tot_cap = {r: sum(CAPT[(h, r)] for h in HUB_CODES) for r in ROLES}
base_dem = {}
for h in HUB_CODES:
    base_dem[(h, "Pilot")] = sum(v for (hh, f), v in pil_dem.items() if hh == h); base_dem[(h, "Cabin Crew")] = sum(v for (hh, b), v in cab_dem.items() if hh == h)
wmap = {"Ground Staff": gnd_w, "Maintenance Engineer": mx_w, "Operations Coordinator": fl_touch}
for r in ("Ground Staff", "Maintenance Engineer", "Operations Coordinator"):
    ws = sum(wmap[r][h] / (HF.get((h, r), 1.0)) for h in HUB_CODES)
    for h in HUB_CODES: base_dem[(h, r)] = tot_cap[r] * 0.60 * 0.96 * (wmap[r][h] / HF.get((h, r), 1.0)) / ws
hist = []; y, m = 2024, 1
while (y, m) <= (2026, 9):
    t_ = (date(y, m, 1) - date(2026, 10, 1)).days / 365; g = 1.04 ** t_; hg = 1.025 ** t_
    for h in HUB_CODES:
        fl = fl_touch[h] * dim(y, m) * SEAS[m] * g
        for r in ROLES:
            dem = base_dem[(h, r)] * SEAS[m] * g * random.uniform(.97, 1.03)
            ab = VAC[m] + SICKR[m] + .03 + random.uniform(-.01, .01); avail = CAPT[(h, r)] / hg * (1 - ab)
            u = dem / avail; ot = max(0, dem - avail * .88) * .6
            hist.append(dict(month=f"{y}-{m:02d}", hub=h, role=r, flights=int(fl), passengers=int(fl * AVGSEAT * SEAS_LF[m] * random.uniform(.98, 1.02)), demand_hours=int(dem),
                             available_hours=int(avail), utilization_pct=round(u * 100, 1), sickness_rate_pct=round((SICKR[m] + random.uniform(-.006, .006)) * 100, 2),
                             overtime_hours=int(ot), cancelled_flights=int(fl * (.004 + .05 * max(0, u - .92)) * random.uniform(.6, 1.4)),
                             delayed_flights_pct=round(min(100.0, 14 + 20 * max(0, u - .85) * 100 / 10 + random.uniform(-2, 2)), 1)))
    m += 1; y, m = (y + 1, 1) if m == 13 else (y, m)
T["monthly_operations_history"] = hist
bud = []; y, m = 2026, 1
while (y, m) <= (2027, 12):
    for h in HUB_CODES:
        for r in ROLES:
            if HC[(h, r)] == 0: continue
            pm = 110 if r == "Pilot" else 140; avgc = sum(CST[(h, r)]) / len(CST[(h, r)]); hcb = int(HC[(h, r)] * 1.01 ** ((date(y, m, 1) - date(2026, 10, 1)).days / 30 / 3))
            lab = hcb * pm * avgc * 1.0; past = (y, m) <= (2026, 9); stress = 1.7 if (h, r) in HF and HF[(h, r)] < .9 else 1.0
            bud.append(dict(month=f"{y}-{m:02d}", hub=h, department=DEPT[r], role=r, budget_headcount=hcb, budget_labor_cost_eur=int(lab), budget_overtime_eur=int(lab * .03), budget_contractor_eur=int(lab * .02),
                            actual_labor_cost_eur=int(lab * random.uniform(.98, 1.03)) if past else None, actual_overtime_eur=int(lab * .03 * stress * random.uniform(.8, 1.3)) if past else None,
                            actual_contractor_eur=int(lab * .02 * stress * random.uniform(.7, 1.4)) if past else None))
    m += 1; y, m = (y + 1, 1) if m == 13 else (y, m)
T["budgets"] = bud

# =====================================================================  SCENARIOS + NESTED HUB JSON
SCEN = [dict(scenario_id="SC1", name="Passenger volume +15%", parameters=dict(passenger_growth_pct=15, scope="all hubs", horizon="next 12 months"), questions=["Which hubs/roles exceed 100% utilization?", "How many extra pilots/cabin crew are needed?"]),
        dict(scenario_id="SC2", name="30 pilots unavailable", parameters=dict(unavailable_pilots=30, hub="AMS", fleet_family="A320FAM", start="2026-11-02", duration_days=14), questions=["Which flights are at risk?", "Who can backfill?"]),
        dict(scenario_id="SC3", name="Storm Aurelia rebalancing", parameters=dict(disruption_group="Storm Aurelia", window="2026-10-29 03:00Z to 2026-10-30 02:00Z"), questions=["Which flights to cancel/retime?", "How to reposition crews and aircraft?"]),
        dict(scenario_id="SC4", name="Open a new hub", parameters=dict(candidate_id="CH1", airport="BRU"), questions=["Headcount per role?", "Cost and ramp-up timeline?"]),
        dict(scenario_id="SC5", name="Summer 2027 peak", parameters=dict(period="2027-07-01..2027-08-31", pending_vacations="treat as approved vs denied"), questions=["Do we have enough pilots?", "Which hubs are short?"]),
        dict(scenario_id="SC6", name="Aircraft AOG cluster", parameters=dict(source="maintenance_activities where aog_flag=1 and status=IN_PROGRESS"), questions=["Which flights lose their aircraft?", "Which spare aircraft can substitute?"])]
def dump_json(obj, path):
    """Pretty-printed UTF-8 JSON: 2-space indent, one field per line, unescaped '/' and non-ASCII."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False); f.write("\n")

dump_json(SCEN, f"{JSON_DIR}/scenarios.json")
nested = []
for h in HUB_CODES:
    nested.append(dict(hub=h, name=AP[h]["name"], country=AP[h]["country"], timezone=AP[h]["tz"], gates=len(GATES_BY_HUB[h]),
        facilities=[{k: v for k, v in fc.items() if k != "hub"} for fc in facilities if fc["hub"] == h],
        aircraft_homed={f: tails_fam_at[h].get(f, 0) for f in FAMS}, headcount={r: HC[(h, r)] for r in ROLES}, monthly_capacity_hours={r: round(CAPT[(h, r)]) for r in ROLES},
        daily_flights_touching_hub=round(fl_touch[h], 1)))
dump_json(nested, f"{JSON_DIR}/hubs_nested.json")
dump_json(con, f"{JSON_DIR}/contractors.json")

# =====================================================================  WRITE (CSV + JSON only)
JSON_MAX_ROWS = 60000   # larger tables are CSV-only
counts = {}
for name, rows in T.items():
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(f"{CSV_DIR}/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="", lineterminator="\n")
        w.writeheader()
        for r in rows: w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    if len(rows) <= JSON_MAX_ROWS and name != "contractors":   # contractors.json is written nested above
        dump_json([{k: r.get(k) for k in cols} for r in rows], f"{JSON_DIR}/{name}.json")
    counts[name] = len(rows)
dump_json(counts, f"{OUT}/_row_counts.json")
print(counts)
