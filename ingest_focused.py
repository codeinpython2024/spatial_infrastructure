import os
import requests
import psycopg2
import time
import json
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "nigeria_infrastructure")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_URL = os.environ.get("DATABASE_URL")

# Overpass API mirrors for OSM queries
overpass_mirrors = [
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter"
]

osm_queries = {
    "Power Substation": 'nwr["power"="substation"](4.0, 2.5, 14.5, 15.0);',
    "Power Plant": 'nwr["power"="plant"](4.0, 2.5, 14.5, 15.0);',
    "Power Generator": 'nwr["power"="generator"](4.0, 2.5, 14.5, 15.0);',
    "Airport": 'nwr["aeroway"="aerodrome"](4.0, 2.5, 14.5, 15.0);',
    "Bus Station": 'nwr["amenity"="bus_station"](4.0, 2.5, 14.5, 15.0);',
    "Government Building": 'nwr["office"="government"](4.0, 2.5, 14.5, 15.0); nwr["amenity"="townhall"](4.0, 2.5, 14.5, 15.0); nwr["amenity"="courthouse"](4.0, 2.5, 14.5, 15.0);',
    "Financial Building": 'nwr["amenity"="bank"](4.0, 2.5, 14.5, 15.0); nwr["amenity"="atm"](4.0, 2.5, 14.5, 15.0);'
}

def query_overpass_with_fallback(name, q_body, timeout=60):
    query_str = f"[out:json][timeout:{timeout}];\n(\n{q_body}\n);\nout center;"
    headers = {
        "User-Agent": "NigeriaCriticalInfrastructureBot/1.0 (https://github.com/spatial-infra; contact@example.com)",
        "Accept": "application/json"
    }
    for mirror in overpass_mirrors:
        print(f"  Trying mirror: {mirror}...")
        is_main_mirror = "z.overpass-api.de" in mirror
        max_attempts = 4 if is_main_mirror else 1
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(mirror, params={'data': query_str}, headers=headers, timeout=timeout + 15)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('elements', [])
                elif response.status_code == 429:
                    wait_time = 20 * (attempt + 1)
                    print(f"  -> Rate limited (429) by {mirror}. Sleeping {wait_time}s before retry (attempt {attempt+1}/{max_attempts})...")
                    time.sleep(wait_time)
                else:
                    print(f"  -> HTTP {response.status_code} from {mirror}. Retrying next mirror...")
                    break
            except Exception as e:
                print(f"  -> Exception from {mirror}: {e}. Retrying next...")
                time.sleep(5)
        time.sleep(5)
    return []

def initialize_boundary_table(conn):
    """Creates the country boundary table and loads the GeoJSON polygon if not present."""
    cur = conn.cursor()
    print("Enabling PostGIS extension if not exists...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    conn.commit()

    cur.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'nigeria_country_boundary');")
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        print("Creating table nigeria_country_boundary...")
        cur.execute("CREATE TABLE nigeria_country_boundary (id serial primary key, geom geometry(MultiPolygon, 4326));")
        conn.commit()
        
    cur.execute("SELECT COUNT(*) FROM nigeria_country_boundary;")
    count = cur.fetchone()[0]
    
    if count == 0:
        print("Loading country boundary GeoJSON into database...")
        geojson_path = "nigeria_boundary.geojson"
        if not os.path.exists(geojson_path):
            geojson_path = os.path.join(os.path.dirname(__file__), "nigeria_boundary.geojson")
        
        if os.path.exists(geojson_path):
            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)
            
            if "features" in geojson_data:
                geom = geojson_data['features'][0]['geometry']
            else:
                geom = geojson_data.get('geometry')
                
            geom_str = json.dumps(geom)
            cur.execute("INSERT INTO nigeria_country_boundary (geom) VALUES (ST_Multi(ST_GeomFromGeoJSON(%s)));", (geom_str,))
            conn.commit()
            print("Successfully loaded country boundary.")
        else:
            print(f"Warning: Boundary GeoJSON file not found at {geojson_path}. Boundary checks might fail if table is empty.")
    cur.close()

def main():
    print("Connecting to PostgreSQL database...")
    try:
        if DB_URL:
            conn = psycopg2.connect(DB_URL)
        else:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
        initialize_boundary_table(conn)
        cur = conn.cursor()
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return

    # First clean up the database of any non-healthcare and non-education assets to ensure no remnants
    print("Cleaning database of existing non-healthcare/education records...")
    cur.execute("DELETE FROM infrastructure_assets WHERE asset_type NOT IN ('healthcare', 'education');")
    conn.commit()

    # Query templates for inserting
    # The WITH clause ensures we do not insert duplicate points spatially (within 50 meters)
    insert_query = """
        INSERT INTO infrastructure_assets (osm_id, source, asset_name, asset_type, sub_type, state, lga, geom)
        SELECT %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        WHERE NOT EXISTS (
            SELECT 1 FROM infrastructure_assets 
            WHERE asset_type = %s
              AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)
        );
    """

    # 1. Ingest GRID3 Energy and Electricity Substations
    print("\nIngesting GRID3 Energy and Electricity Substations...")
    url = "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/Energy_and_electricity_substations_in_Nigeria/FeatureServer/0/query"
    offset = 0
    limit = 2000
    records = []
    
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": limit,
            "f": "json"
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            features = data.get('features', [])
            
            if not features:
                break
            
            for f in features:
                geom = f.get('geometry', {})
                attrs = f.get('attributes', {})
                
                lon = geom.get('x')
                lat = geom.get('y')
                
                if lon is None or lat is None:
                    continue
                
                try:
                    lon_val = float(lon)
                    lat_val = float(lat)
                    if not (2.0 < lon_val < 15.0 and 4.0 < lat_val < 14.5):
                        continue
                except (ValueError, TypeError):
                    continue
                    
                asset_name = attrs.get('ecity_nam') or attrs.get('name') or attrs.get('poi_name')
                if not asset_name or str(asset_name).strip() == '' or str(asset_name).strip().lower() == 'nan':
                    asset_name = "Energy Substation"
                else:
                    asset_name = str(asset_name).strip()
                    
                state = attrs.get('statename') or attrs.get('state')
                if state:
                    state = str(state).strip()
                lga = attrs.get('lganame') or attrs.get('lga')
                if lga:
                    lga = str(lga).strip()
                    
                uniq_id = attrs.get('uniq_id') or attrs.get('FID') or attrs.get('OBJECTID')
                
                records.append((
                    uniq_id,
                    "GRID3 Nigeria - Energy Substations",
                    asset_name,
                    "utility",
                    "Energy Substation",
                    state,
                    lga,
                    lon_val,
                    lat_val,
                    "utility", # for ST_DWithin subquery
                    lon_val,
                    lat_val  # for ST_DWithin subquery
                ))
            
            print(f"  Fetched {offset + len(features)} features...")
            offset += len(features)
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  Error downloading batch at offset {offset}: {e}")
            break
            
    if records:
        print(f"  Inserting {len(records)} records into PostgreSQL...")
        try:
            execute_batch(cur, insert_query, records, page_size=2000)
            conn.commit()
            print("  Successfully ingested GRID3 Energy Substations.")
        except Exception as e:
            conn.rollback()
            print(f"  Error inserting records: {e}")

    # 2. Ingest OSM Overpass API Datasets
    print("\nIngesting OSM Overpass API datasets...")
    for sub_type, query_body in osm_queries.items():
        print(f"Fetching OSM {sub_type}...")
        elements = query_overpass_with_fallback(sub_type, query_body, timeout=60)
        
        if not elements:
            print(f"  No elements found or failed to fetch for {sub_type}.")
            continue
            
        records = []
        if "Government" in sub_type:
            asset_type = "government"
        elif "Financial" in sub_type:
            asset_type = "financial"
        elif "Power" in sub_type or "Water" in sub_type:
            asset_type = "utility"
        else:
            asset_type = "transport"
            
        for el in elements:
            tags = el.get('tags', {})
            lat = el.get('lat') or (el.get('center', {}).get('lat') if el.get('center') else None)
            lon = el.get('lon') or (el.get('center', {}).get('lon') if el.get('center') else None)
            osm_id = el.get('id')
            
            if lat is None or lon is None:
                continue
                
            try:
                lon_val = float(lon)
                lat_val = float(lat)
                if not (2.0 < lon_val < 15.0 and 4.0 < lat_val < 14.5):
                    continue
            except (ValueError, TypeError):
                continue
                
            name = tags.get('name') or tags.get('operator') or f"OSM {sub_type}"
            state = tags.get('addr:state')
            lga = tags.get('addr:city')
            
            records.append((
                osm_id,
                "OpenStreetMap (Overpass API)",
                name.strip(),
                asset_type,
                sub_type,
                state,
                lga,
                lon_val,
                lat_val,
                asset_type, # for ST_DWithin subquery
                lon_val,
                lat_val  # for ST_DWithin subquery
            ))
            
        if records:
            print(f"  Inserting {len(records)} OSM records...")
            try:
                execute_batch(cur, insert_query, records, page_size=2000)
                conn.commit()
                print(f"  Successfully ingested OSM {sub_type}.")
            except Exception as e:
                conn.rollback()
                print(f"  Error inserting records: {e}")
        time.sleep(10)

    # 3. Post-processing: Spatial Nearest-Neighbor state/lga assignment
    print("\nRunning spatial state/lga nearest-neighbor assignment for newly inserted items...")
    spatial_query = """
        UPDATE infrastructure_assets target
        SET state = source.state,
            lga = source.lga
        FROM (
            SELECT DISTINCT ON (t.id) t.id, s.state, s.lga
            FROM infrastructure_assets t
            CROSS JOIN LATERAL (
                SELECT s.state, s.lga
                FROM infrastructure_assets s
                WHERE s.asset_type IN ('healthcare', 'education') 
                  AND s.state IS NOT NULL 
                  AND s.lga IS NOT NULL
                ORDER BY t.geom <-> s.geom
                LIMIT 1
            ) s
            WHERE (t.state IS NULL OR t.lga IS NULL OR t.state = '' OR t.lga = '')
              AND t.asset_type IN ('utility', 'transport', 'government', 'financial')
        ) source
        WHERE target.id = source.id;
    """
    try:
        cur.execute(spatial_query)
        conn.commit()
        print("Successfully aligned administrative boundaries using spatial join.")
    except Exception as e:
        conn.rollback()
        print(f"Error during spatial join: {e}")

    # 4. Clean up out-of-boundary assets for newly ingested types
    print("\nCleaning up out-of-boundary assets...")
    cleanup_query = """
        DELETE FROM infrastructure_assets a
        WHERE a.asset_type IN ('utility', 'transport', 'government', 'financial')
          AND NOT EXISTS (
              SELECT 1 FROM nigeria_country_boundary b
              WHERE ST_Contains(b.geom, a.geom)
          );
    """
    try:
        cur.execute(cleanup_query)
        deleted_count = cur.rowcount
        conn.commit()
        print(f"Successfully removed {deleted_count} out-of-boundary assets.")
    except Exception as e:
        conn.rollback()
        print(f"Error cleaning up out-of-boundary assets: {e}")

    # Check total database counts
    cur.execute("SELECT asset_type, COUNT(*) FROM infrastructure_assets GROUP BY asset_type;")
    print("\nFinal Database Counts:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}")

    cur.close()
    conn.close()
    print("\nFocused Ingestion Completed Successfully!")

if __name__ == "__main__":
    main()
