# Nigeria Critical Infrastructure Mapping Platform

An interactive spatial database, ingestion pipeline, and web application designed to collect, process, validate, and visualize critical infrastructure assets across Nigeria (including healthcare, education, utilities, financial services, and government facilities).

## 🚀 Key Features

* **Interactive Map Interface:** Dynamic geospatial mapping of assets with search capabilities:
  * **Search & Filters:** Real-time name-based search with strict State and Asset Type scoping to prevent nationwide performance overheads.
  * **Themed UI Chrome:** Modern theme toggle switcher that seamlessly assimilates its borders and icons to active themes.
* **Geospatial Ingestion Pipeline:** Automatic extraction and parsing of spatial datasets:
  * **Healthcare Facilities:** Local SQLite-backed GeoPackage (`nga_health_facilities_v2_0.gpkg`).
  * **Educational Facilities:** Shapefile parsing using `pyshp` (`Nigeria_-_Schools/` directory).
  * **Energy Substations:** Live Esri ArcGIS Feature Server query.
  * **Public Infrastructure:** Direct OpenStreetMap querying via Overpass API mirrors.
* **Geospatial Validation & Post-processing:**
  * Auto-assigns State and LGA administrative attributes to assets using a spatial nearest-neighbor join.
  * Cleans up out-of-boundary assets using country boundaries defined in `nigeria_boundary.geojson`.
* **Administrative Controls:** Fully featured admin portal to manually add, edit, or bulk import assets via CSV with:
  * **Spatial Duplicate Check:** Warns administrators on manual creation or edits if an asset of the same type exists within a 50-meter radius, presenting the conflicting asset name, distance, and option to bypass/override.
  * **Spatial LGA Proximity Check:** Warns administrators if a selected location falls far from its declared LGA boundaries (with override).
  * **Feed Search:** Debounced search bar over the paginated manual assets table feed.
* **Robust Verification & Testing:** Built-in integration tests for administrative REST APIs and End-to-End Playwright test suite for browser UI automation.

---

## 🛠️ Technology Stack

* **Backend:** Flask (Python) with Werkzeug secure hashing and logging configuration.
* **Database:** PostgreSQL with **PostGIS** extension for spatial index and geometric queries.
* **Frontend:** HTML5, CSS3, JavaScript, Leaflet mapping library.
* **Dependencies & Tooling:** Managed via `uv` package manager (`pyproject.toml` and `uv.lock`).
* **Tests:** Python `unittest` framework and `playwright` for end-to-end integration tests.

---

## 📂 Project Structure

```
├── .env.example              # Template for environment configuration
├── .gitignore                # Git ignore rules for virtualenvs, secrets, and large spatial datasets
├── pyproject.toml            # Python dependencies and metadata (Managed via uv/pip)
├── uv.lock                   # Pinned dependency lockfile
├── database.py               # PostgreSQL/PostGIS connection pooling
├── main.py                   # Main Flask application and REST API endpoints
├── ingest_data.py            # Main ingestion script for all spatial data sources
├── ingest_focused.py         # Incremental/Focused ingestion for live OSM & utility data
├── nigeria_boundary.geojson  # GeoJSON polygon definition of Nigeria's borders
├── templates/                # HTML Jinja templates for views
│   ├── index.html            # Main map dashboard interface
│   ├── admin_login.html      # Secure admin login form
│   └── admin_dashboard.html  # Admin CRUD dashboard, bulk CSV upload, and pagination
├── static/                   # Static styling and frontend logic
│   ├── css/style.css         # Theme styles, dashboard components, and responsive grid layouts
│   ├── js/main.js            # Public map UI handlers
│   └── js/map.js             # Leaflet GIS visualization logic
└── tests/                    # Test suites
    ├── test_admin_api.py     # Backend REST API integration test coverage
    └── test_ui_playwright.py # Playwright End-to-End browser UI test coverage
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root of the project using the configuration below:

```env
# Database Credentials
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_postgres_user
DB_PASS=your_postgres_password
DB_NAME=nigeria_infrastructure

# Flask Settings
SECRET_KEY=generate_a_secure_random_hex_string

# Admin Login Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$xFrabuNUAEcTebGi$d4b76cc8d0d12c0f2bb4bf09686835b8fb9fdf4330304be98b387f5d44e719873bd7c923c7885c5c1141d2462b10c671c50ff74bb483e1b73fff6bae3624ae92
```

> [!NOTE]
> The default `ADMIN_PASSWORD_HASH` corresponds to the password `admin123`.

---

## 🚀 Getting Started

### 1. Database Setup
Make sure your PostgreSQL instance is running and has the **PostGIS** extension enabled.
```sql
CREATE DATABASE nigeria_infrastructure;
\c nigeria_infrastructure;
CREATE EXTENSION postgis;
```

### 2. Install Dependencies
Ensure you have Python `>= 3.14` and dependencies installed using `uv` (recommended) or `pip`:
```bash
# Using uv (fastest)
uv sync

# Using pip
pip install -r pyproject.toml
```

### 3. Run Ingestion Pipeline
To seed the database with spatial boundaries, shapefile data, and health facility coordinates:
```bash
python ingest_data.py
```
To perform a live Overpass and Utility update:
```bash
python ingest_focused.py
```

### 4. Run the Flask Web Application
```bash
python main.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## 🧪 Testing

### API Unit Tests
To verify CRUD operations, LGA proximity calculations, boundary warnings, and overrides:
```bash
python -m unittest test_admin_api.py
```

### E2E UI Tests
To run the automated browser tests verifying login flow, file dropzone handlers, CSV parsing, and UI pagination via Playwright:
```bash
python test_ui_playwright.py
```