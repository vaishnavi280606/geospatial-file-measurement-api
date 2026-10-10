# Geospatial File Measurement API

FastAPI service that accepts KML files or ZIP archives containing a Shapefile, extracts feature data, and returns CRS-aware measurements.

## Setup

Requirements: Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `/docs`.

Run tests with:

```powershell
python -m pytest
```

## API

### Upload and process a file

`POST /api/files/`

Send a multipart form field named `file`. Accepted files are `.kml` and `.zip` archives containing at least `.shp`, `.dbf`, and preferably `.shx` and `.prj` files.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/files/ -F "file=@survey.kml"
```

Example response:

```json
{
  "id": "f4a7c8...",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-10T12:00:00+00:00"
}
```

### Get file information

`GET /api/files/{id}/`

Returns the upload summary shown above. Unknown IDs return `404`.

### Get measurements

`GET /api/files/{id}/measurements/`

Returns every extracted feature with its ID, geometry type, GeoJSON geometry, source CRS, properties, measurement, unit, and measurement status.

```json
{
  "file_id": "f4a7c8...",
  "crs": "EPSG:4326",
  "measurements": [
    {
      "id": 0,
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": []},
      "crs": "EPSG:4326",
      "properties": {"name": "Survey area"},
      "measurement": 123456.7,
      "measurement_unit": "square_meters",
      "measurement_status": "COMPLETED"
    }
  ]
}
```

Polygon and MultiPolygon features return area in square meters. LineString and MultiLineString features return length in meters. Point features return `measurement_status: "NOT_REQUIRED"`; other geometry types return `"UNSUPPORTED"` with a null measurement rather than failing the whole file. Features from a Shapefile without CRS metadata return `"CRS_REQUIRED"` for measurable geometries rather than calculating misleading values.

## Architecture

- `app/main.py` creates the FastAPI application and health endpoint.
- `app/api.py` validates uploads, invokes processing, and exposes the three API endpoints.
- `app/processing.py` parses KML with the standard XML library and zipped Shapefiles with GeoPandas.
- `app/models.py` contains the in-memory file record used by this single-process implementation.

The upload flow writes the incoming bytes to a temporary directory, parses all features, calculates measurements, and stores the completed result under a generated ID. Temporary files are removed after processing.

For geographic CRS data such as EPSG:4326, the service estimates a local UTM CRS from the feature bounds before calculating area or length. Projected source data is measured in its native CRS. KML is defined by the KML specification as WGS84/EPSG:4326. Shapefile CRS is read from its `.prj` file; when it is absent, the response reports `UNKNOWN` and measurements should be treated as requiring a known CRS.

## Design decisions

FastAPI was selected for its typed request handling, automatic OpenAPI documentation, and straightforward file-upload support. GeoPandas provides reliable Shapefile reading and CRS transformations. KML is parsed directly to avoid relying on optional GDAL KML driver support across platforms.

The repository is intentionally in memory to keep the assessment service small and easy to run. A production deployment should use object storage for uploads, a database for metadata and results, background jobs for large files, and configured upload-size/time limits. Authentication, rate limiting, richer KML geometry support, pagination, and persistent processing statuses are also future scope.

## Learning and future scope

This project demonstrates practical geospatial parsing, GeoPandas/Shapely geometry operations, projected CRS selection, multipart API design, and testable FastAPI service boundaries. Future improvements would include asynchronous job processing, persistent storage, stronger schema validation, expanded KML style and nested geometry support, and deployment automation.