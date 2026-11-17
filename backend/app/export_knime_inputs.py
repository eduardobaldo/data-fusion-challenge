import csv
import json
from pathlib import Path

from .config import settings
from .db import connect_db, mongo_client


def run():
    raw_dir = settings.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        client = mongo_client()
        docs = client[settings.mongo_database]["osm_responses"].find().sort("fetched_at", -1).limit(1)
        doc = next(docs, None)
        client.close()
    except Exception:
        doc = None
    raw_dir.joinpath("osm_latest.json").write_text(json.dumps(doc["payload"], ensure_ascii=False, default=str) if doc else '{"elements":[]}', encoding="utf-8")
    with connect_db() as conn:
        venue_rows = conn.execute("""SELECT osm_type,osm_id,name,latitude,longitude,address,city,region,source
            FROM venues ORDER BY city,name""").fetchall()
        matches = conn.execute("""SELECT m.id, v.name AS venue_name, v.city, m.starts_at, m.capacity,
            count(a.id) AS attendee_count FROM matches m JOIN venues v ON v.id=m.venue_id
            LEFT JOIN attendees a ON a.match_id=m.id GROUP BY m.id,v.name,v.city,m.starts_at,m.capacity""").fetchall()
    with raw_dir.joinpath("venues.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["osm_type","osm_id","name","latitude","longitude","address","city","region","source"])
        writer.writeheader()
        for row in venue_rows:
            writer.writerow(dict(row))
    with raw_dir.joinpath("matches.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(matches[0].keys()) if matches else ["id","venue_name","city","starts_at","capacity","attendee_count"])
        writer.writeheader()
        for row in matches:
            item = dict(row)
            starts_at = item["starts_at"]
            item["starts_at"] = starts_at.isoformat() if hasattr(starts_at, "isoformat") else str(starts_at)
            writer.writerow(item)
    print(f"Entradas para KNIME exportadas para {raw_dir}")


if __name__ == "__main__":
    run()
