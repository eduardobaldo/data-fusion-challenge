from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

import duckdb
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import connect_db, init_db, match_dict, mongo_status, record_raw, seed_match_if_empty
from .schemas import AttendanceCreate, MatchCreate, VenueInput

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_match_if_empty()
    yield


app = FastAPI(title="Futebol de Bairro API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    try:
        with connect_db() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "city": settings.demo_city, "stores": {"sqlite": "connected", "duckdb": "local", "mongodb": mongo_status()}}
    except Exception as exc:
        raise HTTPException(503, "Banco de dados indisponível") from exc


@app.get("/api/config")
def public_config():
    return {"city": settings.demo_city, "region": settings.demo_region, "country": settings.demo_country}


@app.get("/api/venues")
def venues(search: str = Query(default="", max_length=100)):
    with connect_db() as conn:
        now = datetime.now(timezone.utc).isoformat()
        rows = conn.execute("""SELECT v.id,v.name,v.latitude,v.longitude,v.address,v.city,v.region,v.source,v.updated_at,
            count(DISTINCT CASE WHEN m.starts_at > ? THEN m.id END) AS upcoming_matches
            FROM venues v LEFT JOIN matches m ON m.venue_id=v.id
            WHERE v.city=? AND (? = '' OR lower(v.name) LIKE lower(?) OR lower(v.address) LIKE lower(?) OR lower(v.city) LIKE lower(?))
            GROUP BY v.id ORDER BY v.name""", (now, settings.demo_city, search, f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    return [{**dict(row), "updated_at": row["updated_at"]} for row in rows]


@app.post("/api/venues", status_code=201)
def add_venue(payload: VenueInput):
    with connect_db() as conn:
        row = conn.execute("""INSERT INTO venues(osm_type,osm_id,name,latitude,longitude,address,city,region,source)
            VALUES ('manual',?,?,?,?,?,?,?,'manual') RETURNING id""",
            (str(uuid4()),payload.name.strip(),payload.latitude,payload.longitude,payload.address.strip(),settings.demo_city,settings.demo_region)).fetchone()
    return {"id": row["id"], "name": payload.name.strip(), "source": "manual"}


@app.patch("/api/venues/{venue_id}")
def edit_venue(venue_id: int, payload: VenueInput):
    with connect_db() as conn:
        row = conn.execute("""UPDATE venues SET name=?,latitude=?,longitude=?,address=?,source='manual',updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND city=? RETURNING id""",
            (payload.name.strip(),payload.latitude,payload.longitude,payload.address.strip(),venue_id,settings.demo_city)).fetchone()
    if not row:
        raise HTTPException(404, "Campo não encontrado nesta cidade")
    return {"id": row["id"], "name": payload.name.strip(), "source": "manual"}


def get_match(match_id: int):
    with connect_db() as conn:
        row = conn.execute("""SELECT m.id,m.title,m.starts_at,m.capacity,m.organizer_name,m.created_at,
            v.id AS venue_id,v.name AS venue_name,v.address AS venue_address,v.latitude,v.longitude,v.city,v.region,
            count(a.id) AS attendee_count
            FROM matches m JOIN venues v ON v.id=m.venue_id LEFT JOIN attendees a ON a.match_id=m.id
            WHERE m.id=? GROUP BY m.id,v.id""", (match_id,)).fetchone()
        if not row:
            return None
        attendees = conn.execute("SELECT display_name FROM attendees WHERE match_id=? ORDER BY joined_at", (match_id,)).fetchall()
    item = match_dict(row)
    item["attendees"] = [person["display_name"] for person in attendees]
    return item


@app.get("/api/matches")
def matches(upcoming: bool = True):
    where = "WHERE m.starts_at > ?" if upcoming else ""
    with connect_db() as conn:
        city_filter = "AND v.city=?" if where else "WHERE v.city=?"
        params = (datetime.now(timezone.utc).isoformat(), settings.demo_city) if where else (settings.demo_city,)
        ids = conn.execute(f"SELECT m.id FROM matches m JOIN venues v ON v.id=m.venue_id {where} {city_filter} ORDER BY m.starts_at LIMIT 100", params).fetchall()
    return [get_match(row["id"]) for row in ids]


@app.post("/api/matches", status_code=201)
def create_match(payload: MatchCreate):
    with connect_db() as conn:
        venue = conn.execute("SELECT id FROM venues WHERE id=? AND city=?", (payload.venue_id,settings.demo_city)).fetchone()
        if not venue:
            raise HTTPException(404, "Campo não encontrado")
        row = conn.execute("""INSERT INTO matches(venue_id,title,starts_at,capacity,organizer_name)
            VALUES (?,?,?,?,?) RETURNING id""", (payload.venue_id,payload.title,payload.starts_at.astimezone(timezone.utc).isoformat(),payload.capacity,payload.organizer_name.strip())).fetchone()
        key = payload.organizer_name.strip().casefold()
        conn.execute("INSERT INTO attendees(match_id,display_name,participant_key) VALUES (?,?,?)", (row["id"],payload.organizer_name.strip(),key))
    return get_match(row["id"])


@app.post("/api/matches/{match_id}/attendees", status_code=201)
def join_match(match_id: int, payload: AttendanceCreate):
    key = payload.display_name.strip().casefold()
    if not key:
        raise HTTPException(422, "Informe seu nome")
    try:
        with connect_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            match = conn.execute("SELECT id,capacity,starts_at FROM matches WHERE id=?", (match_id,)).fetchone()
            if not match:
                raise HTTPException(404, "Partida não encontrada")
            if match["starts_at"] <= datetime.now(timezone.utc).isoformat():
                raise HTTPException(409, "A partida já começou")
            count = conn.execute("SELECT count(*) AS n FROM attendees WHERE match_id=?", (match_id,)).fetchone()["n"]
            if count >= match["capacity"]:
                raise HTTPException(409, "A partida já atingiu o limite de participantes")
            conn.execute("INSERT INTO attendees(match_id,display_name,participant_key) VALUES (?,?,?)", (match_id,payload.display_name.strip(),key))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Esse nome já confirmou presença nesta partida") from exc
    return get_match(match_id)


@app.delete("/api/matches/{match_id}/attendees/{display_name}")
def leave_match(match_id: int, display_name: str):
    key = display_name.strip().casefold()
    with connect_db() as conn:
        result = conn.execute("DELETE FROM attendees WHERE match_id=? AND participant_key=?", (match_id,key))
        if result.rowcount == 0:
            raise HTTPException(404, "Confirmação não encontrada")
    return get_match(match_id)


@app.get("/api/venues/{venue_id}/forecast")
async def forecast(venue_id: int, starts_at: datetime):
    with connect_db() as conn:
        venue = conn.execute("SELECT id,name,latitude,longitude FROM venues WHERE id=?", (venue_id,)).fetchone()
    if not venue:
        raise HTTPException(404, "Campo não encontrado")
    if starts_at.tzinfo is None:
        raise HTTPException(422, "Informe data e hora com fuso horário")
    now = datetime.now(timezone.utc)
    if starts_at < now or starts_at > now + timedelta(days=7):
        raise HTTPException(422, "A previsão está disponível para os próximos sete dias")
    try:
        # forecast_days inclui o dia atual; oito dias cobrem partidas marcadas
        # para qualquer horário dentro dos próximos sete dias.
        params = {"latitude": venue["latitude"], "longitude": venue["longitude"], "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code", "timezone": settings.demo_timezone, "forecast_days": 8}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(settings.open_meteo_url, params=params, headers={"User-Agent": "FutebolDeBairro/1.0 (educational demo)"})
            response.raise_for_status()
            payload = response.json()
        local_time = starts_at.astimezone(ZoneInfo(settings.demo_timezone)).replace(minute=0, second=0, microsecond=0)
        times = payload.get("hourly", {}).get("time", [])
        target = local_time.strftime("%Y-%m-%dT%H:00")
        try:
            idx = times.index(target)
        except ValueError:
            raise HTTPException(503, "Previsão indisponível para esse horário")
        hourly = payload["hourly"]
        result = {key: values[idx] if idx < len(values) else None for key, values in hourly.items() if key != "time"}
        fetched_at = datetime.now(timezone.utc)
        record_raw("weather_responses", {"provider": "Open-Meteo", "venue_id": venue_id, "starts_at": starts_at, "fetched_at": fetched_at, "payload": payload})
        return {"venue_id": venue_id, "venue_name": venue["name"], "starts_at": starts_at.isoformat(), "local_time": target, "provider": "Open-Meteo", "fetched_at": fetched_at.isoformat(), "units": payload.get("hourly_units", {}), "forecast": result}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning("Open-Meteo respondeu HTTP %s", exc.response.status_code)
        raise HTTPException(503, f"Open-Meteo respondeu com erro HTTP {exc.response.status_code}. Tente novamente mais tarde.") from exc
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning("Não foi possível conectar ao Open-Meteo: %s", type(exc).__name__)
        raise HTTPException(503, "Não foi possível acessar o serviço de clima. Verifique a internet e tente novamente.") from exc
    except Exception as exc:
        logger.exception("Falha inesperada ao consultar Open-Meteo")
        raise HTTPException(503, "Previsão do tempo indisponível no momento") from exc


@app.get("/api/metrics")
def metrics():
    try:
        with duckdb.connect(str(settings.duckdb_path), read_only=True) as con:
            rows = con.execute("SELECT metric,dimension,value,generated_at FROM metrics WHERE dimension IN (?, 'Geral') ORDER BY metric,dimension", (settings.demo_city,)).fetchall()
        return [{"metric": row[0], "dimension": row[1], "value": row[2], "generated_at": row[3].isoformat() if row[3] else None} for row in rows]
    except Exception:
        return []


@app.post("/api/admin/run-knime-import")
def run_knime_import():
    from .load_knime_outputs import run
    try:
        run()
        return {"status": "ok", "message": "Saídas KNIME importadas para SQLite e DuckDB"}
    except SystemExit as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "Falha ao importar as saídas KNIME") from exc
