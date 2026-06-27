from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import get_db_connection, release_db_connection
import logging
import requests
import json
import time
import os
from functools import wraps
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "b9165384bc133f81e812d4d98d41cf07bb0b81c2f9011be1b54b005166b26d37")
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        env_username = os.environ.get('ADMIN_USERNAME', 'admin')
        env_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
        
        # In case the hash wasn't configured, fallback to default hash of 'admin123'
        if not env_password_hash:
            # Hash for 'admin123'
            env_password_hash = "scrypt:32768:8:1$xFrabuNUAEcTebGi$d4b76cc8d0d12c0f2bb4bf09686835b8fb9fdf4330304be98b387f5d44e719873bd7c923c7885c5c1141d2462b10c671c50ff74bb483e1b73fff6bae3624ae92"

        if username == env_username and check_password_hash(env_password_hash, password):
            session['logged_in'] = True
            logger.info("Admin logged in successfully.")
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid username or password"
            logger.warning(f"Failed login attempt for user: {username}")

    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    """Admin logout."""
    session.pop('logged_in', None)
    logger.info("Admin logged out.")
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin control panel dashboard."""
    # Fetch states and asset types for dynamic dropdowns
    conn = get_db_connection()
    if not conn:
        return "Database connection unavailable", 500
        
    try:
        with conn.cursor() as cursor:
            # Fetch recent 10 manually inserted assets
            cursor.execute("""
                SELECT id, asset_name, asset_type, sub_type, state, lga, ST_Y(geom) as lat, ST_X(geom) as lon
                FROM infrastructure_assets
                WHERE source = 'Admin Portal'
                ORDER BY id DESC
                LIMIT 10;
            """)
            recent_assets = []
            for row in cursor.fetchall():
                recent_assets.append({
                    'id': row[0],
                    'name': row[1],
                    'type': row[2],
                    'sub_type': row[3],
                    'state': row[4],
                    'lga': row[5],
                    'lat': row[6],
                    'lon': row[7]
                })
            return render_template('admin_dashboard.html', recent_assets=recent_assets)
    except Exception as e:
        logger.exception("Error loading admin dashboard:")
        return f"Error loading dashboard: {e}", 500
    finally:
        release_db_connection(conn)


@app.route('/')
def index():
    """Renders the main dashboard mapping interface."""
    return render_template('index.html')

@app.route('/api/v1/states', methods=['GET'])
def get_states():
    """Returns a list of all unique states containing infrastructure assets."""
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection unavailable for fetching states.")
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT state FROM infrastructure_assets WHERE state IS NOT NULL ORDER BY state;")
            states = [row[0] for row in cursor.fetchall()]
            return jsonify({"states": states})
    except Exception as e:
        logger.exception("Error fetching unique states:")
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/asset-types', methods=['GET'])
def get_asset_types():
    """Returns a list of all unique asset types containing infrastructure assets."""
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection unavailable for fetching asset types.")
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT asset_type FROM infrastructure_assets WHERE asset_type IS NOT NULL ORDER BY asset_type;")
            asset_types = [row[0] for row in cursor.fetchall()]
            return jsonify({"asset_types": asset_types})
    except Exception as e:
        logger.exception("Error fetching unique asset types:")
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/infrastructure', methods=['GET'])
def get_infrastructure():
    """
    API endpoint to dynamically filter assets by State and Asset Type.
    Returns standard RFC 7946 compliant GeoJSON features.
    """
    state_filter = request.args.get('state', None)
    type_filter = request.args.get('type', None)

    conn = get_db_connection()
    if not conn:
        logger.error("Database connection unavailable for fetching infrastructure.")
        return jsonify({"error": "Database connection unavailable"}), 500

    # Construct safe parameterized SQL query with PostGIS GeoJSON serialization.
    # COALESCE ensures we always return a valid empty features array instead of null when no records match.
    query = """
        SELECT jsonb_build_object(
            'type',     'FeatureCollection',
            'features', COALESCE(jsonb_agg(features.feature), '[]'::jsonb)
        )
        FROM (
            SELECT jsonb_build_object(
                'type',       'Feature',
                'id',         id,
                'geometry',   ST_AsGeoJSON(geom)::jsonb,
                'properties', jsonb_build_object(
                    'name', asset_name,
                    'source', source,
                    'type', asset_type,
                    'sub_type', sub_type,
                    'state', state,
                    'lga', lga
                )
            ) AS feature
            FROM infrastructure_assets
            WHERE 1=1
    """
    
    params = []
    has_filters = False
    if state_filter:
        query += " AND state = %s"
        params.append(state_filter)
        has_filters = True
    if type_filter:
        query += " AND asset_type = %s"
        params.append(type_filter)
        has_filters = True

    query += " ORDER BY id"
    if not has_filters:
        query += " LIMIT 5000"

    query += ") features;"

    try:
        with conn.cursor() as cursor:
            logger.info(f"Executing query with filters state={state_filter}, type={type_filter}")
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            geojson_data = result[0] if result and result[0] else {"type": "FeatureCollection", "features": []}
            return jsonify(geojson_data)
    except Exception as e:
        logger.exception("Error executing infrastructure query:")
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/population', methods=['GET'])
def get_population():
    """
    On-demand endpoint to query WorldPop population estimates for a specific location.
    Calculates population in a 1km x 1km box (0.01 degree buffer) around the coordinate.
    """
    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')

    if not lat_str or not lon_str:
        return jsonify({"error": "Latitude and longitude parameters are required"}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({"error": "Latitude and longitude must be valid floating point numbers"}), 400

    # Create a bounding box polygon (approx. 1km x 1km buffer around point)
    buffer = 0.01
    min_lat = lat - buffer
    max_lat = lat + buffer
    min_lon = lon - buffer
    max_lon = lon + buffer

    geojson_polygon = {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }

    try:
        logger.info(f"Querying WorldPop for point ({lat}, {lon})")
        # Submit the request to WorldPop REST API synchronously
        worldpop_url = "https://api.worldpop.org/v1/services/stats"
        payload = {
            "dataset": "wpgppop",
            "year": "2020",
            "geojson": json.dumps(geojson_polygon),
            "runasync": "false"
        }
        submit_res = requests.get(worldpop_url, params=payload, timeout=30)
        submit_res.raise_for_status()
        submit_data = submit_res.json()

        if submit_data.get('error'):
            logger.error(f"WorldPop API error: {submit_data.get('error_message')}")
            return jsonify({"error": submit_data.get('error_message')}), 500

        # Check if returned synchronously
        total_population = None
        data_field = submit_data.get('data')
        if data_field and isinstance(data_field, dict):
            total_population = data_field.get('total_population')

        # Fallback to polling if the server processes it asynchronously
        if total_population is None:
            task_id = submit_data.get('taskid')
            if not task_id:
                logger.error("No task ID or data returned from WorldPop API")
                return jsonify({"error": "Failed to retrieve population data"}), 500
            
            logger.info(f"Synchronous data not available. Polling task {task_id}...")
            status_url = f"https://api.worldpop.org/v1/tasks/{task_id}"
            
            for attempt in range(15):
                time.sleep(1.0)
                status_res = requests.get(status_url, timeout=10)
                status_res.raise_for_status()
                status_data = status_res.json()

                if status_data.get('status') == 'finished' or status_data.get('data'):
                    data_field_poll = status_data.get('data')
                    if data_field_poll and isinstance(data_field_poll, dict):
                        total_population = data_field_poll.get('total_population')
                        if total_population is not None:
                            break
                elif status_data.get('status') == 'failed':
                    logger.error(f"WorldPop task failed: {status_data.get('error_message')}")
                    break

        if total_population is None:
            return jsonify({"error": "WorldPop population query timed out or failed"}), 504

        return jsonify({
            "lat": lat,
            "lon": lon,
            "total_population": round(total_population)
        })

    except Exception as e:
        logger.exception("Error during WorldPop population lookup:")
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/lgas', methods=['GET'])
def get_lgas():
    """Returns a list of unique LGAs for a specified state, or all unique LGAs."""
    state = request.args.get('state')
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection unavailable"}), 500
    try:
        with conn.cursor() as cursor:
            if state:
                cursor.execute("SELECT DISTINCT lga FROM infrastructure_assets WHERE state = %s AND lga IS NOT NULL ORDER BY lga;", (state,))
            else:
                cursor.execute("SELECT DISTINCT lga FROM infrastructure_assets WHERE lga IS NOT NULL ORDER BY lga;")
            lgas = [row[0] for row in cursor.fetchall()]
            return jsonify({"lgas": lgas})
    except Exception as e:
        logger.exception("Error fetching LGAs:")
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/admin/assets', methods=['GET'])
def get_admin_assets():
    """Returns a paginated list of manual assets created by admins."""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1:
            page = 1
        if limit < 1:
            limit = 10
    except ValueError:
        page = 1
        limit = 10

    offset = (page - 1) * limit

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with conn.cursor() as cursor:
            # Get total count of manual assets
            cursor.execute("""
                SELECT COUNT(*) FROM infrastructure_assets
                WHERE source = 'Admin Portal';
            """)
            total_count = cursor.fetchone()[0]

            # Fetch current page of manual assets
            cursor.execute("""
                SELECT id, asset_name, asset_type, sub_type, state, lga, ST_Y(geom) as lat, ST_X(geom) as lon
                FROM infrastructure_assets
                WHERE source = 'Admin Portal'
                ORDER BY id DESC
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            
            assets = []
            for row in cursor.fetchall():
                assets.append({
                    'id': row[0],
                    'name': row[1],
                    'type': row[2],
                    'sub_type': row[3],
                    'state': row[4],
                    'lga': row[5],
                    'lat': row[6],
                    'lon': row[7]
                })
            
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "success": True,
                "assets": assets,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }), 200
    except Exception as e:
        logger.exception("Error loading admin assets:")
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/admin/upload-csv', methods=['POST'])
def upload_csv():
    """Parses a CSV file containing administrative assets, validates them, and performs a bulk insert."""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Only CSV files are supported"}), 400

    import csv
    import io

    conn = None
    try:
        # Read the file content and parse CSV
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)
        
        # Verify required headers
        required_headers = {'asset_name', 'asset_type', 'sub_type', 'state', 'lga', 'latitude', 'longitude'}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            return jsonify({"error": f"CSV must contain headers: {', '.join(required_headers)}"}), 400

        rows = list(reader)
        if not rows:
            return jsonify({"error": "CSV file is empty"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection unavailable"}), 500

        inserted_count = 0
        failed_count = 0
        warnings = []
        errors = []
        
        with conn.cursor() as cursor:
            for idx, row in enumerate(rows, start=1):
                name = row.get('asset_name')
                asset_type = row.get('asset_type')
                sub_type = row.get('sub_type') or 'General'
                state = row.get('state')
                lga = row.get('lga') or 'N/A'
                lat_str = row.get('latitude')
                lon_str = row.get('longitude')
                
                if not all([name, asset_type, state, lat_str, lon_str]):
                    failed_count += 1
                    errors.append(f"Row {idx}: Missing required fields.")
                    continue
                
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except ValueError:
                    failed_count += 1
                    errors.append(f"Row {idx}: Coordinates must be valid floating point numbers.")
                    continue
                
                # 1. Spatial check against country boundary
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM nigeria_country_boundary
                        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    );
                """, (lon, lat))
                inside_nigeria = cursor.fetchone()[0]
                if not inside_nigeria:
                    failed_count += 1
                    errors.append(f"Row {idx}: coordinates ({lat}, {lon}) are outside of Nigeria's boundaries.")
                    continue

                # 2. LGA Proximity check (warn if distance > 25km)
                cursor.execute("""
                    SELECT MIN(ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography))
                    FROM infrastructure_assets
                    WHERE state = %s AND lga = %s AND geom IS NOT NULL;
                """, (lon, lat, state, lga))
                row_dist = cursor.fetchone()
                min_dist = row_dist[0] if row_dist else None
                
                if min_dist is not None and min_dist > 25000:
                    distance_km = round(min_dist / 1000, 1)
                    warnings.append(f"Row {idx}: '{name}' is {distance_km} km away from other assets in {lga}.")

                # 3. Perform insertion
                cursor.execute("""
                    INSERT INTO infrastructure_assets (source, asset_name, asset_type, sub_type, state, lga, geom)
                    VALUES ('Admin Portal', %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
                """, (name, asset_type, sub_type, state, lga, lon, lat))
                inserted_count += 1
            
            # Commit all successful insertions
            conn.commit()
            
        return jsonify({
            "success": True,
            "message": f"CSV import finished. Successfully inserted {inserted_count} rows, failed {failed_count} rows.",
            "total_rows": len(rows),
            "inserted_rows": inserted_count,
            "failed_rows": failed_count,
            "warnings": warnings,
            "errors": errors
        }), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.exception("Error processing CSV file:")
        return jsonify({"error": f"Failed to process CSV file: {str(e)}"}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route('/api/v1/admin/add-asset', methods=['POST'])
def add_asset():
    """Validates boundary rules, proximity rules, and inserts a manual infrastructure asset."""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    asset_name = data.get('asset_name')
    asset_type = data.get('asset_type')
    sub_type = data.get('sub_type')
    state = data.get('state')
    lga = data.get('lga')
    lat_str = data.get('lat')
    lon_str = data.get('lon')
    override_lga_check = data.get('override_lga_check', False)

    if not all([asset_name, asset_type, state, lat_str, lon_str]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({"error": "Latitude and longitude must be valid numbers"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with conn.cursor() as cursor:
            # 1. Spatial check against country boundary
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM nigeria_country_boundary
                    WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                );
            """, (lon, lat))
            inside_nigeria = cursor.fetchone()[0]
            
            if not inside_nigeria:
                return jsonify({"error": "Coordinates are outside of Nigeria's boundaries."}), 400

            # 2. LGA Proximity check (warn if point is > 25km away from existing assets in this LGA)
            if not override_lga_check:
                cursor.execute("""
                    SELECT MIN(ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography))
                    FROM infrastructure_assets
                    WHERE state = %s AND lga = %s AND geom IS NOT NULL;
                """, (lon, lat, state, lga))
                row = cursor.fetchone()
                min_dist = row[0] if row else None
                
                if min_dist is not None and min_dist > 25000:
                    distance_km = round(min_dist / 1000, 1)
                    return jsonify({
                        "lga_warning": True,
                        "distance_km": distance_km,
                        "message": f"Coordinates are {distance_km} km away from other assets in {lga}. It may fall outside the selected LGA's boundary. Do you want to save anyway?"
                    }), 200

            # 3. Perform insertion
            cursor.execute("""
                INSERT INTO infrastructure_assets (source, asset_name, asset_type, sub_type, state, lga, geom)
                VALUES ('Admin Portal', %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                RETURNING id;
            """, (asset_name, asset_type, sub_type or 'General', state, lga or 'N/A', lon, lat))
            
            new_id = cursor.fetchone()[0]
            conn.commit()
            
            logger.info(f"Admin manually added asset {new_id} - {asset_name}")
            return jsonify({
                "success": True,
                "asset": {
                    "id": new_id,
                    "name": asset_name,
                    "type": asset_type,
                    "sub_type": sub_type or 'General',
                    "state": state,
                    "lga": lga or 'N/A',
                    "lat": lat,
                    "lon": lon
                }
            }), 201
    except Exception as e:
        logger.exception("Error adding administrative asset:")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/admin/edit-asset/<int:asset_id>', methods=['POST', 'PUT'])
def edit_asset(asset_id):
    """Validates boundary rules, proximity rules, and updates an existing manual infrastructure asset."""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    asset_name = data.get('asset_name')
    asset_type = data.get('asset_type')
    sub_type = data.get('sub_type')
    state = data.get('state')
    lga = data.get('lga')
    lat_str = data.get('lat')
    lon_str = data.get('lon')
    override_lga_check = data.get('override_lga_check', False)

    if not all([asset_name, asset_type, state, lat_str, lon_str]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({"error": "Latitude and longitude must be valid numbers"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with conn.cursor() as cursor:
            # Verify asset exists and is manually added
            cursor.execute("SELECT id FROM infrastructure_assets WHERE id = %s AND source = 'Admin Portal';", (asset_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Asset not found or not editable"}), 404

            # 1. Spatial check against country boundary
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM nigeria_country_boundary
                    WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                );
            """, (lon, lat))
            inside_nigeria = cursor.fetchone()[0]
            
            if not inside_nigeria:
                return jsonify({"error": "Coordinates are outside of Nigeria's boundaries."}), 400

            # 2. LGA Proximity check
            if not override_lga_check:
                cursor.execute("""
                    SELECT MIN(ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography))
                    FROM infrastructure_assets
                    WHERE state = %s AND lga = %s AND geom IS NOT NULL AND id != %s;
                """, (lon, lat, state, lga, asset_id))
                row = cursor.fetchone()
                min_dist = row[0] if row else None
                
                if min_dist is not None and min_dist > 25000:
                    distance_km = round(min_dist / 1000, 1)
                    return jsonify({
                        "lga_warning": True,
                        "distance_km": distance_km,
                        "message": f"Coordinates are {distance_km} km away from other assets in {lga}. It may fall outside the selected LGA's boundary. Do you want to update anyway?"
                    }), 200

            # 3. Perform update
            cursor.execute("""
                UPDATE infrastructure_assets 
                SET asset_name = %s, asset_type = %s, sub_type = %s, state = %s, lga = %s, 
                    geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                WHERE id = %s AND source = 'Admin Portal';
            """, (asset_name, asset_type, sub_type or 'General', state, lga or 'N/A', lon, lat, asset_id))
            
            conn.commit()
            
            logger.info(f"Admin manually updated asset {asset_id} - {asset_name}")
            return jsonify({
                "success": True,
                "asset": {
                    "id": asset_id,
                    "name": asset_name,
                    "type": asset_type,
                    "sub_type": sub_type or 'General',
                    "state": state,
                    "lga": lga or 'N/A',
                    "lat": lat,
                    "lon": lon
                }
            }), 200
    except Exception as e:
        logger.exception("Error updating administrative asset:")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/v1/admin/delete-asset/<int:asset_id>', methods=['POST', 'DELETE'])
def delete_asset(asset_id):
    """Deletes a manual infrastructure asset."""
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection unavailable"}), 500
    
    try:
        with conn.cursor() as cursor:
            # Ensure it is a manual asset to prevent database corruption
            cursor.execute("SELECT id FROM infrastructure_assets WHERE id = %s AND source = 'Admin Portal';", (asset_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({"error": "Asset not found or not created via Admin Portal"}), 404
            
            cursor.execute("DELETE FROM infrastructure_assets WHERE id = %s;", (asset_id,))
            conn.commit()
            logger.info(f"Admin deleted manual asset {asset_id}")
            return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error deleting administrative asset:")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        release_db_connection(conn)

if __name__ == '__main__':
    # Set debug=False in a production environment
    app.run(host='0.0.0.0', port=5000, debug=True)