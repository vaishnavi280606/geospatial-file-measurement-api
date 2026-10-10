from fastapi import FastAPI

from app.api import router

app = FastAPI(
    title="Geospatial File Measurement API",
    version="0.1.0",
    description="Upload KML or zipped Shapefiles and retrieve CRS-aware measurements.",
)
app.include_router(router, prefix="/api")


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": "Geospatial File Measurement API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
