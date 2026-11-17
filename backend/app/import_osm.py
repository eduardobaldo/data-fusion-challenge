import json
import time
from datetime import datetime, timezone

import httpx

from .config import settings
from .db import connect_db, record_raw

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def run():
    south, west, north, east = [float(value.strip()) for value in settings.overpass_bbox.split(",")]
    bbox = f"{south},{west},{north},{east}"
    query = f"""[out:json][timeout:60];
    (nwr[leisure~\"pitch|sports_centre\"]({bbox}); nwr[sport~\"soccer|football\"]({bbox}););
    out center tags;"""
    payload = None
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                response = httpx.post(endpoint, data={"data": query}, timeout=90, headers={"User-Agent": "FutebolDeBairro/1.0 (educational demo)"})
                response.raise_for_status()
                payload = response.json()
                print(f"Dados recebidos de {endpoint}")
                break
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{endpoint}: {exc}")
                if attempt == 0:
                    time.sleep(2)
        if payload is not None:
            break

    if payload is None:
        print("Não foi possível consultar o Overpass neste momento. Os campos já salvos localmente foram mantidos.")
        for error in errors:
            print(f"- {error}")
        return
    fetched_at = datetime.now(timezone.utc)
    raw_saved = record_raw("osm_responses", {"source": "Overpass API / OpenStreetMap", "fetched_at": fetched_at, "query": query, "payload": payload})

    count = 0
    with connect_db() as conn:
        for item in payload.get("elements", []):
            tags = item.get("tags", {})
            coords = item.get("center") or item
            lat, lon = coords.get("lat"), coords.get("lon")
            if lat is None or lon is None:
                continue
            name = tags.get("name") or tags.get("leisure") or "Campo esportivo sem nome"
            address = " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber"), tags.get("addr:suburb")]))
            conn.execute("""INSERT INTO venues(osm_type,osm_id,name,latitude,longitude,address,city,region,source,updated_at)
                VALUES (?,?,?,?,?,?,?,?,'openstreetmap',?)
                ON CONFLICT(osm_type,osm_id) DO UPDATE SET name=excluded.name, latitude=excluded.latitude,
                longitude=excluded.longitude, address=excluded.address, updated_at=excluded.updated_at""",
                (item["type"], str(item["id"]), name, lat, lon, address, settings.demo_city, settings.demo_region, fetched_at.isoformat()))
            count += 1
    print(f"Importados/atualizados {count} campos de OpenStreetMap em {settings.demo_city}. Documento bruto no Atlas: {'sim' if raw_saved else 'não' }.")


if __name__ == "__main__":
    run()
