from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class FileRecord:
    id: str
    filename: str
    feature_count: int
    crs: str
    status: str
    features: list[dict[str, Any]]
    created_at: datetime
