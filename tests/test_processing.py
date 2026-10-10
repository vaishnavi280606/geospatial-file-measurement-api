from pathlib import Path

from app.processing import process_file


KML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>
<Placemark><name>Square</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
0,0 0,0.01 0.01,0.01 0.01,0 0,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>Route</name><LineString><coordinates>0,0 0.01,0</coordinates></LineString></Placemark>
<Placemark><name>Origin</name><Point><coordinates>0,0</coordinates></Point></Placemark>
</Document></kml>"""


def test_kml_features_are_measured_in_metric_units(tmp_path: Path) -> None:
    crs, features = process_file("survey.kml", KML.encode())

    assert crs == "EPSG:4326"
    assert len(features) == 3
    assert features[0]["geometry_type"] == "Polygon"
    assert features[0]["measurement_unit"] == "square_meters"
    assert features[0]["measurement"] > 1_000_000
    assert features[1]["measurement_unit"] == "meters"
    assert features[1]["measurement"] > 1_000
    assert features[2]["measurement_status"] == "NOT_REQUIRED"


def test_unknown_crs_does_not_crash_measurement_pipeline() -> None:
    from shapely.geometry import LineString
    from app.processing import _measure_features

    features = [{"index": 0, "geometry": LineString([(0, 0), (1, 1)]), "properties": {}}]

    result = _measure_features(features, "UNKNOWN")

    assert result[0]["measurement_status"] == "CRS_REQUIRED"
    assert result[0]["measurement"] is None
