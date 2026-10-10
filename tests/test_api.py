from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_and_measurements() -> None:
    kml = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Point><coordinates>0,0</coordinates></Point></Placemark></kml>'''
    response = client.post("/api/files/", files={"file": ("point.kml", kml, "application/vnd.google-earth.kml+xml")})
    assert response.status_code == 201
    file_id = response.json()["id"]

    measurements = client.get(f"/api/files/{file_id}/measurements/")
    assert measurements.status_code == 200
    assert measurements.json()["measurements"][0]["measurement_status"] == "NOT_REQUIRED"


def test_upload_rejects_unsupported_extension() -> None:
    response = client.post("/api/files/", files={"file": ("notes.txt", b"not geospatial", "text/plain")})

    assert response.status_code == 400
