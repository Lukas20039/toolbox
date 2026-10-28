"""Toolbox web app: static tool page plus server-side converters."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import images, media, pdf, settings

app = FastAPI(title="Toolbox", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(pdf.router)
app.include_router(images.router)
app.include_router(media.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {
        "maxUploadMb": settings.MAX_UPLOAD_MB,
        "maxMediaDurationMin": settings.MAX_MEDIA_DURATION_MIN,
        "urlDownload": settings.ENABLE_URL_DOWNLOAD,
        "allowedMediaHosts": settings.ALLOWED_MEDIA_HOSTS,
    }


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
