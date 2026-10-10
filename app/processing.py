"""Geospatial parsing and CRS-aware measurement logic."""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import geopandas as gpd
from shapely.geometry import mapping

SUPPORTED_EXTENSIONS = {".kml", ".zip"}
KML_NAMESPACE = "{http://www.opengis.net/kml/2.2}"


class ProcessingError(ValueError):
	"""Raised when an uploaded file cannot be processed."""


def process_file(filename: str, content: bytes) -> tuple[str, list[dict[str, Any]]]:
	extension = Path(filename).suffix.lower()
	if extension not in SUPPORTED_EXTENSIONS:
		raise ProcessingError("Only .kml files or .zip Shapefile archives are supported")

	with tempfile.TemporaryDirectory() as directory:
		source = Path(directory) / Path(filename).name
		source.write_bytes(content)
		if extension == ".kml":
			crs, features = _read_kml(source)
		else:
			crs, features = _read_shapefile_archive(source, Path(directory) / "unzipped")

	return crs, _measure_features(features, crs)


def _read_shapefile_archive(source: Path, extraction_directory: Path) -> tuple[str, list[dict[str, Any]]]:
	try:
		with zipfile.ZipFile(source) as archive:
			members = [member for member in archive.namelist() if not member.is_dir()]
			if not any(Path(member).suffix.lower() == ".shp" for member in members):
				raise ProcessingError("The ZIP archive does not contain a .shp file")
			extraction_directory.mkdir(parents=True, exist_ok=True)
			root = extraction_directory.resolve()
			for member in members:
				target = (extraction_directory / member).resolve()
				if root not in target.parents:
					raise ProcessingError("The ZIP archive contains an unsafe path")
			archive.extractall(extraction_directory)
	except zipfile.BadZipFile as exc:
		raise ProcessingError("The uploaded .zip file is invalid") from exc

	shapefiles = [path for path in extraction_directory.rglob("*") if path.suffix.lower() == ".shp"]
	try:
		frame = gpd.read_file(shapefiles[0])
	except Exception as exc:
		raise ProcessingError(f"Unable to read the Shapefile: {exc}") from exc
	return _crs_name(frame.crs), _frame_features(frame)


def _read_kml(source: Path) -> tuple[str, list[dict[str, Any]]]:
	try:
		root = ElementTree.parse(source).getroot()
	except ElementTree.ParseError as exc:
		raise ProcessingError("The uploaded KML file is invalid XML") from exc

	features: list[dict[str, Any]] = []
	geometry_tags = {"Point", "LineString", "Polygon", "MultiGeometry"}
	for index, placemark in enumerate(root.iter(f"{KML_NAMESPACE}Placemark")):
		geometry_element = next(
			(child for child in placemark if child.tag.rsplit("}", 1)[-1] in geometry_tags),
			None,
		)
		if geometry_element is None:
			continue
		geometry = _kml_geometry(geometry_element)
		if geometry is None:
			continue
		properties: dict[str, Any] = {}
		name = placemark.findtext(f"{KML_NAMESPACE}name")
		if name is not None:
			properties["name"] = name
		for data in placemark.findall(f".//{KML_NAMESPACE}Data"):
			key = data.attrib.get("name")
			value = data.findtext(f"{KML_NAMESPACE}value")
			if key:
				properties[key] = value
		features.append({"index": index, "geometry": geometry, "properties": properties})
	return "EPSG:4326", features


def _kml_geometry(element: ElementTree.Element) -> Any | None:
	from shapely.geometry import GeometryCollection, LineString, Point, Polygon

	tag = element.tag.rsplit("}", 1)[-1]
	if tag == "MultiGeometry":
		geometries = [item for child in element if (item := _kml_geometry(child)) is not None]
		return GeometryCollection(geometries) if geometries else None

	coordinates = element.find(f".//{KML_NAMESPACE}coordinates")
	if coordinates is None or not coordinates.text:
		return None
	points = []
	for raw_point in re.split(r"\s+", coordinates.text.strip()):
		values = raw_point.split(",")
		if len(values) >= 2:
			points.append((float(values[0]), float(values[1])))
	if tag == "Point" and points:
		return Point(points[0])
	if tag == "LineString" and len(points) >= 2:
		return LineString(points)
	if tag == "Polygon" and len(points) >= 4:
		return Polygon(points)
	return None


def _frame_features(frame: gpd.GeoDataFrame) -> list[dict[str, Any]]:
	features = []
	for index, row in frame.iterrows():
		properties = {str(key): _json_value(value) for key, value in row.drop(labels="geometry").to_dict().items()}
		features.append({"index": int(index), "geometry": row.geometry, "properties": properties})
	return features


def _measure_features(features: list[dict[str, Any]], crs: str) -> list[dict[str, Any]]:
	if crs == "UNKNOWN":
		return [_unmeasured_feature(feature, "CRS_REQUIRED") for feature in features]
	measurement_crs = _measurement_crs(features, crs)
	geometries = gpd.GeoSeries([item["geometry"] for item in features], crs=crs)
	projected = geometries if crs == measurement_crs else geometries.to_crs(measurement_crs)
	results = []
	for feature, projected_geometry in zip(features, projected):
		geometry = feature["geometry"]
		geometry_type = geometry.geom_type
		result: dict[str, Any] = {
			"id": feature["index"],
			"geometry_type": geometry_type,
			"geometry": mapping(geometry),
			"crs": crs,
			"properties": feature["properties"],
			"measurement": None,
			"measurement_unit": None,
			"measurement_status": "NOT_REQUIRED" if geometry_type == "Point" else "UNSUPPORTED",
		}
		if geometry_type in {"Polygon", "MultiPolygon"}:
			result.update(measurement=float(projected_geometry.area), measurement_unit="square_meters", measurement_status="COMPLETED")
		elif geometry_type in {"LineString", "MultiLineString"}:
			result.update(measurement=float(projected_geometry.length), measurement_unit="meters", measurement_status="COMPLETED")
		results.append(result)
	return results


def _unmeasured_feature(feature: dict[str, Any], status: str) -> dict[str, Any]:
	geometry = feature["geometry"]
	geometry_type = geometry.geom_type
	return {
		"id": feature["index"],
		"geometry_type": geometry_type,
		"geometry": mapping(geometry),
		"crs": "UNKNOWN",
		"properties": feature["properties"],
		"measurement": None,
		"measurement_unit": None,
		"measurement_status": "NOT_REQUIRED" if geometry_type == "Point" else status,
	}


def _measurement_crs(features: list[dict[str, Any]], crs: str) -> str:
	if not features:
		return crs
	source = gpd.GeoSeries([item["geometry"] for item in features], crs=crs)
	if source.crs and source.crs.is_geographic:
		estimated = source.estimate_utm_crs()
		if estimated is not None:
			return estimated.to_string()
	return crs


def _crs_name(crs: Any) -> str:
	return "UNKNOWN" if crs is None else crs.to_string()


def _json_value(value: Any) -> Any:
	return value.item() if hasattr(value, "item") else value
