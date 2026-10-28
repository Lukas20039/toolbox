"""Temp-directory and upload helpers."""

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from . import settings

CHUNK = 1024 * 1024


def new_workdir() -> Path:
    return Path(tempfile.mkdtemp(dir=settings.WORK_DIR))


def safe_name(name: str, fallback: str = "file") -> str:
    """Strip directories and characters that are awkward in file names."""
    name = Path(name or "").name
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', "_", name).strip(" .")
    return name[:150] or fallback


def save_upload(upload: UploadFile, workdir: Path, allowed_ext: set[str] | None = None) -> Path:
    name = safe_name(upload.filename or "")
    ext = Path(name).suffix.lower().lstrip(".")
    if allowed_ext is not None and ext not in allowed_ext:
        raise HTTPException(400, f"Dateityp .{ext or '?'} nicht unterstützt. Erlaubt: {', '.join(sorted(allowed_ext))}")
    dest = workdir / name
    # Avoid collisions when several uploads share a name.
    i = 1
    while dest.exists():
        dest = workdir / f"{Path(name).stem}_{i}{Path(name).suffix}"
        i += 1
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    with dest.open("wb") as fh:
        while chunk := upload.file.read(CHUNK):
            written += len(chunk)
            if written > limit:
                raise HTTPException(413, f"Datei größer als {settings.MAX_UPLOAD_MB} MB")
            fh.write(chunk)
    if written == 0:
        raise HTTPException(400, f"Datei {name} ist leer")
    return dest


def zip_files(paths: list[Path], dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, p.name)
    return dest


def send_and_cleanup(path: Path, workdir: Path, filename: str | None = None, media_type: str | None = None) -> FileResponse:
    return FileResponse(
        path,
        filename=filename or path.name,
        media_type=media_type,
        background=BackgroundTask(shutil.rmtree, workdir, ignore_errors=True),
    )
