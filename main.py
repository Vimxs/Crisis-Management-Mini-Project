"""CRIS backend (FastAPI + PostgreSQL/PostGIS), as proposed in Review I.
Priority engine, resource allocation, live data (Open-Meteo, USGS, OpenStreetMap, OSRM).
Run: docker compose up -d db  ->  uvicorn main:app --reload"""
import math, os, random
from pathlib import Path
from dotenv import load_dotenv
import psycopg, requests
from psycopg.rows import dict_row
from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")
DSN = os.getenv("DATABASE_URL", "postgresql://postgres:cris@localhost:5432/cris")
UA = {"User-Agent": "CRIS-student-project/1.0"}
app = FastAPI(title="Crisis Response Intelligence System API")

W = {"severity": .30, "impact": .25, "urgency": .20, "vulnerability": .15, "accessibility": .10}
NEEDS = {"collapse": {"rescue": 2, "ambulance": 2}, "flood": {"rescue": 1, "medical": 1},
         "fire": {"rescue": 1, "ambulance": 1}, "accident": {"ambulance": 1}, "medical": {"medical": 1}}
PT = "ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography"
XY = "ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng"

def q(sql, args=(), one=False):
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as c:
        cur = c.execute(sql, args)
        if cur.description is None: return None
        return cur.fetchone() if one else cur.fetchall()

def err(msg, code=502): return JSONResponse({"error": msg}, status_code=code)

def new_inc(name, typ, loc, lat, lng, people, sev, urg, vul=50, acc=60, rain=None):
    impact = min(100, round(25 + people * 0.4))
    q(f"INSERT INTO incidents(name,type,location,geom,people,rain_mm,rain_src,severity,impact,urgency,vulnerability,accessibility)"
      f" VALUES(%s,%s,%s,{PT},%s,%s,%s,%s,%s,%s,%s,%s)",
      (name, typ, loc, lng, lat, people, rain, "manual" if rain is not None else None, sev, impact, urg, vul, acc))

def seed():
    q("TRUNCATE allocations, resources, incidents RESTART IDENTITY CASCADE")
    new_inc("Building Collapse", "collapse", "Yelahanka", 13.1007, 77.5963, 120, 90, 95, 70, 60)
    new_inc("Flash Flood", "flood", "Hebbal", 13.0358, 77.5970, 300, 60, 80, 75, 50, rain=140)
    new_inc("Road Accident", "accident", "Hebbal Flyover", 13.0450, 77.5940, 15, 65, 85, 40, 80)
    new_inc("Fire", "fire", "Rajajinagar", 12.9910, 77.5550, 40, 70, 75, 50, 70)
    new_inc("Medical Emergency", "medical", "Jayanagar", 12.9250, 77.5938, 8, 50, 70, 60, 85)
    pos = {"ambulance": [(13.08, 77.60), (13.02, 77.59), (12.98, 77.57), (12.95, 77.58)],
           "rescue": [(13.07, 77.58), (13.01, 77.55), (12.97, 77.60)],
           "medical": [(13.04, 77.62), (12.99, 77.54), (12.93, 77.60)]}
    for t, ps in pos.items():
        for n, (la, lo) in enumerate(ps):
            q(f"INSERT INTO resources(id,type,name,geom,source) VALUES(%s,%s,%s,{PT},'seed')",
              (f"{t[0].upper()}-{n+1:02d}", t, f"{t.title()} unit {n+1}", lo, la))

@app.on_event("startup")
def startup():
    q((BASE / "schema.sql").read_text())
    if q("SELECT count(*) AS n FROM incidents", one=True)["n"] == 0: seed()

def km(a, b):
    p = math.pi / 180
    h = (math.sin((b["lat"] - a["lat"]) * p / 2) ** 2 +
         math.cos(a["lat"] * p) * math.cos(b["lat"] * p) * math.sin((b["lng"] - a["lng"]) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))

def road(a, b):
    """Road distance/time from OSRM (free); falls back to PostGIS/straight-line distance at 30 km/h."""
    try:
        r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{a['lng']},{a['lat']};{b['lng']},{b['lat']}",
                         params={"overview": "false"}, timeout=4, headers=UA).json()["routes"][0]
        return r["distance"] / 1000, r["duration"] / 60, "OSRM road"
    except Exception:
        d = a["d"] / 1000; return d, d * 2, "straight-line (PostGIS)"

def flood_risk(rain):
    """Hazard model: logistic on 24h rainfall (mm). Replace with a trained Scikit-learn model."""
    return round(100 / (1 + math.exp(-(rain - 80) / 20)))

def score(i):
    f = dict(i["factors"])
    if i["type"] == "flood" and i.get("rain_mm") is not None:
        f["severity"] = max(f["severity"], flood_risk(i["rain_mm"]))
    parts = {k: W[k] * f[k] for k in W}
    total = round(sum(parts.values()))
    top = sorted(parts, key=parts.get, reverse=True)[:2]
    label = "CRITICAL" if total >= 80 else "HIGH" if total >= 65 else "MEDIUM"
    why = f"Driven mainly by {top[0]} ({f[top[0]]}) and {top[1]} ({f[top[1]]}); {i['people']} people affected."
    if i["type"] == "flood" and i.get("rain_mm") is not None:
        why += f" Rainfall {i['rain_mm']} mm gives flood-risk {flood_risk(i['rain_mm'])}."
    return total, label, why

def state():
    res = q(f"SELECT id,name,type,{XY},incident_id AS incident,source FROM resources ORDER BY id")
    out = []
    for r in q(f"SELECT id,name,type,location,{XY},people,rain_mm,rain_src,severity,impact,urgency,vulnerability,accessibility FROM incidents"):
        i = {k: r[k] for k in ("id", "name", "type", "location", "lat", "lng", "people", "rain_mm", "rain_src")}
        i["needs"] = NEEDS[i["type"]]
        i["factors"] = {k: r[k] for k in W}
        s, l, w = score(i)
        out.append({**i, "score": s, "label": l, "explanation": w,
                    "assigned": [x["id"] for x in res if x["incident"] == i["id"]]})
    out.sort(key=lambda x: -x["score"])
    hist = q("SELECT incident,incident_id,resource,type,km,eta_min,via,created_at::text AS at FROM allocations ORDER BY id DESC LIMIT 8")
    return dict(incidents=out, resources=res, weights=W, mode="PostgreSQL + PostGIS", history=hist,
                stats=dict(active=len(out), critical=sum(x["label"] == "CRITICAL" for x in out),
                           available=sum(r["incident"] is None for r in res),
                           deployed=sum(r["incident"] is not None for r in res)))

@app.get("/")
def home(): return FileResponse(BASE / "static" / "index.html")

@app.get("/api/state")
def api_state(): return state()

@app.post("/api/incidents")
def create(d: dict = Body(...)):
    if d.get("type") not in NEEDS: return err("bad type", 400)
    new_inc(d.get("name") or d["type"].title(), d["type"], d.get("location", "Custom"), float(d["lat"]), float(d["lng"]),
            int(d.get("people", 10)), int(d.get("severity", 60)), int(d.get("urgency", 60)))
    return state()

@app.patch("/api/incidents/{iid}")
def update(iid: int, d: dict = Body(...)):
    if not q("SELECT 1 FROM incidents WHERE id=%s", (iid,), one=True): return err("not found", 404)
    for k, v in d.items():
        if k in W: q(f"UPDATE incidents SET {k}=%s WHERE id=%s", (max(0, min(100, int(v))), iid))
        elif k == "rain_mm": q("UPDATE incidents SET rain_mm=%s, rain_src='manual' WHERE id=%s", (float(v), iid))
    return state()

@app.post("/api/incidents/{iid}/resolve")
def resolve(iid: int):
    q("DELETE FROM incidents WHERE id=%s", (iid,))
    return state()

@app.post("/api/simulate")
def simulate():
    typ = random.choice(list(NEEDS))
    new_inc(f"{typ.title()} (simulated)", typ, "Bengaluru", round(12.97 + random.uniform(-.12, .12), 4),
            round(77.60 + random.uniform(-.12, .12), 4), random.randint(5, 250), random.randint(40, 95),
            random.randint(40, 95), random.randint(30, 90), random.randint(30, 90))
    return state()

@app.post("/api/allocate")
def allocate():
    """Highest priority first; per needed type, take the 3 nearest free units (PostGIS), pick the fastest by road."""
    plan = []
    for i in state()["incidents"]:
        for t, n in i["needs"].items():
            have = q("SELECT count(*) AS n FROM resources WHERE incident_id=%s AND type=%s", (i["id"], t), one=True)["n"]
            for _ in range(n - have):
                free = q(f"SELECT id,{XY}, ST_Distance(geom,{PT}) AS d FROM resources "
                         "WHERE type=%s AND incident_id IS NULL ORDER BY d LIMIT 3", (i["lng"], i["lat"], t))
                if not free:
                    plan.append(dict(incident=i["name"], type=t, resource=None)); break
                r, d, m, via = min(((r, *road(r, i)) for r in free), key=lambda x: x[2])
                q("UPDATE resources SET incident_id=%s WHERE id=%s", (i["id"], r["id"]))
                rec = dict(incident=i["name"], incident_id=i["id"], resource=r["id"], type=t, km=round(d, 1), eta_min=round(m), via=via)
                q("INSERT INTO allocations(incident_id,incident,resource,type,km,eta_min,via) VALUES(%(incident_id)s,%(incident)s,%(resource)s,%(type)s,%(km)s,%(eta_min)s,%(via)s)", rec)
                plan.append(rec)
    return dict(plan=plan, **state())

@app.post("/api/reset")
def reset():
    seed(); return state()

@app.post("/api/refresh-weather")
def weather():
    """Live 24h rainfall (Open-Meteo, free, no key) for flood incidents."""
    try:
        for i in q(f"SELECT id,{XY} FROM incidents WHERE type='flood'"):
            r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=8, headers=UA,
                params=dict(latitude=i["lat"], longitude=i["lng"], hourly="precipitation", past_hours=24, forecast_hours=1)).json()
            mm = round(sum(x or 0 for x in r["hourly"]["precipitation"]), 1)
            q("UPDATE incidents SET rain_mm=%s, rain_src='Open-Meteo' WHERE id=%s", (mm, i["id"]))
        return state()
    except Exception as e:
        return err(f"Open-Meteo unreachable: {e}")

@app.post("/api/sync-resources")
def sync():
    """Real hospital / fire-station locations from OpenStreetMap (Overpass, free)."""
    qry = ('[out:json][timeout:25];(nwr["amenity"="hospital"](around:15000,12.9716,77.5946);'
           'nwr["amenity"="fire_station"](around:15000,12.9716,77.5946););out center 80;')
    try:
        els = requests.post("https://overpass-api.de/api/interpreter", data={"data": qry}, timeout=30, headers=UA).json()["elements"]
        pt = lambda e: (e.get("lat") or e["center"]["lat"], e.get("lon") or e["center"]["lon"])
        hosp = [e for e in els if e["tags"].get("amenity") == "hospital"][:12]
        fire = [e for e in els if e["tags"].get("amenity") == "fire_station"][:6]
        if not hosp + fire: return err("no OSM results")
        q("UPDATE resources SET incident_id=NULL"); q("DELETE FROM resources")
        cnt = {"ambulance": 0, "medical": 0, "rescue": 0}
        for n, e in enumerate(hosp + fire):
            t = "rescue" if e in fire else ("ambulance" if n % 2 == 0 else "medical")
            cnt[t] += 1; la, lo = pt(e)
            q(f"INSERT INTO resources(id,type,name,geom,source) VALUES(%s,%s,%s,{PT},'OpenStreetMap')",
              (f"{t[0].upper()}-{cnt[t]:02d}", t, e["tags"].get("name", t.title()), lo, la))
        return state()
    except Exception as e:
        return err(f"Overpass unreachable: {e}")

@app.get("/api/live")
def live():
    """Latest earthquakes M4.5+ (USGS, free)."""
    try:
        fs = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson", timeout=8, headers=UA).json()["features"]
        return dict(quakes=[dict(mag=f["properties"]["mag"], place=f["properties"]["place"], time=f["properties"]["time"]) for f in fs[:6]])
    except Exception as e:
        return err(f"USGS unreachable: {e}")
