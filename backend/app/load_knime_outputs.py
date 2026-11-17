import csv
from datetime import datetime, timezone

import duckdb

from .config import settings
from .db import connect_db


def run():
    processed = settings.data_dir / "processed"
    venues_path = processed / "venues.csv"
    metrics_path = processed / "metrics.csv"
    if not venues_path.exists() or not metrics_path.exists():
        raise SystemExit("Saídas ausentes. Execute o workflow KNIME descrito em knime/README.md primeiro.")
    with venues_path.open(encoding="utf-8-sig", newline="") as f:
        venues = list(csv.DictReader(f))
    with connect_db() as conn:
        for row in venues:
            if row.get("osm_type") and row.get("osm_id"):
                conn.execute("""INSERT INTO venues(osm_type,osm_id,name,latitude,longitude,address,city,region,source)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(osm_type,osm_id) DO UPDATE SET name=excluded.name,latitude=excluded.latitude,
                    longitude=excluded.longitude,address=excluded.address,city=excluded.city,region=excluded.region,source=excluded.source,updated_at=CURRENT_TIMESTAMP""",
                    (row["osm_type"], row["osm_id"], row["name"], float(row["latitude"]), float(row["longitude"]), row.get("address", ""), row.get("city", settings.demo_city), row.get("region", settings.demo_region), row.get("source", "openstreetmap")))
    with metrics_path.open(encoding="utf-8-sig", newline="") as f:
        metrics = list(csv.DictReader(f))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(settings.duckdb_path)) as con:
        con.execute("DELETE FROM metrics")
        for row in metrics:
            if "metric" in row and "value" in row:
                con.execute("INSERT INTO metrics VALUES (?, ?, ?, ?)", (row["metric"], row.get("dimension", "Geral"), float(row["value"] or 0), datetime.now(timezone.utc).replace(tzinfo=None)))
            else:
                # Also accept KNIME's wide-format output if the team chooses that layout.
                for metric in ("partidas_total", "participantes_total", "ocupacao_media"):
                    if metric in row and row[metric] not in (None, ""):
                        con.execute("INSERT INTO metrics VALUES (?, ?, ?, ?)", (metric, row.get("city", "Geral"), float(row[metric]), datetime.now(timezone.utc).replace(tzinfo=None)))
    print(f"Importadas {len(venues)} linhas de campos e {len(metrics)} indicadores.")


if __name__ == "__main__":
    run()
