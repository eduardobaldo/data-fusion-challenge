import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import duckdb
from pymongo import MongoClient

from .config import settings

logger = logging.getLogger(__name__)
_mongo_available = False

DEMO_VENUES = [
    {"osm_type": "demo", "osm_id": "campo-01", "name": "Campo Demonstrativo — Parque A", "latitude": -23.5505, "longitude": -46.6333, "address": "Centro, São Paulo — local de demonstração", "city": "São Paulo", "region": "SP", "source": "demo"},
    {"osm_type": "demo", "osm_id": "campo-02", "name": "Quadra Demonstrativa — Parque B", "latitude": -23.5631, "longitude": -46.6544, "address": "Bela Vista, São Paulo — local de demonstração", "city": "São Paulo", "region": "SP", "source": "demo"},
    {"osm_type": "demo", "osm_id": "campo-03", "name": "Campo Demonstrativo — Parque C", "latitude": -23.5350, "longitude": -46.6250, "address": "Bom Retiro, São Paulo — local de demonstração", "city": "São Paulo", "region": "SP", "source": "demo"},
]


@contextmanager
def connect_db():
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mongo_client():
    if not settings.mongo_url:
        raise RuntimeError("MONGO_URL não configurada. Adicione a URI do MongoDB Atlas ao arquivo .env.")
    return MongoClient(settings.mongo_url, serverSelectionTimeoutMS=4000)


def init_db():
    with connect_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS venues (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              osm_type TEXT NOT NULL,
              osm_id TEXT NOT NULL,
              name TEXT NOT NULL,
              latitude REAL NOT NULL,
              longitude REAL NOT NULL,
              address TEXT NOT NULL DEFAULT '',
              city TEXT NOT NULL,
              region TEXT NOT NULL,
              source TEXT NOT NULL DEFAULT 'openstreetmap',
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(osm_type, osm_id)
            );
            CREATE TABLE IF NOT EXISTS matches (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
              title TEXT NOT NULL,
              starts_at TEXT NOT NULL,
              capacity INTEGER NOT NULL CHECK(capacity BETWEEN 2 AND 30),
              organizer_name TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendees (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
              display_name TEXT NOT NULL,
              participant_key TEXT NOT NULL,
              joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(match_id, participant_key)
            );
        """)
        count = conn.execute("SELECT count(*) AS n FROM venues").fetchone()["n"]
        if count == 0 and settings.demo_city == "São Paulo":
            conn.executemany("""INSERT INTO venues
                (osm_type,osm_id,name,latitude,longitude,address,city,region,source)
                VALUES (:osm_type,:osm_id,:name,:latitude,:longitude,:address,:city,:region,:source)
                ON CONFLICT(osm_type,osm_id) DO NOTHING""", DEMO_VENUES)

    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(settings.duckdb_path)) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS metrics (
            metric TEXT, dimension TEXT, value DOUBLE, generated_at TIMESTAMP
        )""")


def record_raw(collection: str, document: dict) -> bool:
    global _mongo_available
    client = None
    try:
        client = mongo_client()
        client.admin.command("ping")
        client[settings.mongo_database][collection].insert_one(document)
        _mongo_available = True
        return True
    except Exception:
        _mongo_available = False
        logger.warning("Falha ao salvar documento bruto no MongoDB Atlas (%s). Verifique MONGO_URL, usuário/senha e permissões da coleção.", collection, exc_info=False)
        return False
    finally:
        if client is not None:
            client.close()


def mongo_status() -> str:
    global _mongo_available
    client = None
    try:
        client = mongo_client()
        client.admin.command("ping")
        _mongo_available = True
        return "connected"
    except Exception:
        _mongo_available = False
        return "not_configured" if not settings.mongo_url else "unavailable"
    finally:
        if client is not None:
            client.close()


def iso(dt):
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return dt


def seed_match_if_empty():
    with connect_db() as conn:
        venue = conn.execute("SELECT id FROM venues WHERE city=? ORDER BY id LIMIT 1", (settings.demo_city,)).fetchone()
        n = conn.execute("SELECT count(*) AS n FROM matches m JOIN venues v ON v.id=m.venue_id WHERE v.city=?", (settings.demo_city,)).fetchone()["n"]
        if not n and venue:
            starts = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
            row = conn.execute("""INSERT INTO matches(venue_id,title,starts_at,capacity,organizer_name)
                VALUES (?,?,?,?,?) RETURNING id""", (venue["id"], "Racha de demonstração", starts.isoformat(), 10, "Organização")).fetchone()
            conn.execute("INSERT INTO attendees(match_id,display_name,participant_key) VALUES (?,?,?)", (row["id"], "Organização", "organização"))


def match_dict(row):
    item = dict(row)
    item["starts_at"] = item["starts_at"] if isinstance(item["starts_at"], str) else iso(item["starts_at"])
    item["created_at"] = item["created_at"] if isinstance(item["created_at"], str) else iso(item["created_at"])
    return item
