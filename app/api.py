from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models import FileRecord
from app.processing import ProcessingError, process_file

router = APIRouter()
_records: dict[str, FileRecord] = {}


@router.post("/files/", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
	filename = file.filename or "upload"
	if Path(filename).suffix.lower() not in {".kml", ".zip"}:
		raise HTTPException(status_code=400, detail="Only .kml files or .zip Shapefile archives are supported")
	try:
		crs, features = process_file(filename, await file.read())
	except ProcessingError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=422, detail=f"Unable to process file: {exc}") from exc

	record = FileRecord(uuid4().hex, filename, len(features), crs, "COMPLETED", features, datetime.now(timezone.utc))
	_records[record.id] = record
	return _file_summary(record)


@router.get("/files/{file_id}/")
def get_file(file_id: str) -> dict[str, Any]:
	return _file_summary(_get_record(file_id))


@router.get("/files/{file_id}/measurements/")
def get_measurements(file_id: str) -> dict[str, Any]:
	record = _get_record(file_id)
	return {"file_id": record.id, "crs": record.crs, "measurements": record.features}


def _get_record(file_id: str) -> FileRecord:
	record = _records.get(file_id)
	if record is None:
		raise HTTPException(status_code=404, detail="File not found")
	return record


def _file_summary(record: FileRecord) -> dict[str, Any]:
	return {
		"id": record.id,
		"filename": record.filename,
		"feature_count": record.feature_count,
		"crs": record.crs,
		"status": record.status,
		"created_at": record.created_at.isoformat(),
	}
