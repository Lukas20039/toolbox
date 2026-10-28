"""PDF endpoints: merge, split, compress, rotate, protect, convert."""

import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from . import settings
from .files import new_workdir, safe_name, save_upload, send_and_cleanup, zip_files

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff"}
OFFICE_EXT = {"doc", "docx", "odt", "rtf", "txt", "xls", "xlsx", "ods", "csv", "ppt", "pptx", "odp", "html"}


def _reader(path: Path, password: str | None = None) -> PdfReader:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(password or ""):
            raise HTTPException(400, "PDF ist passwortgeschützt – falsches oder fehlendes Passwort")
        return reader
    except PdfReadError as e:
        raise HTTPException(400, f"Ungültige PDF-Datei: {e}") from e


def parse_ranges(spec: str, page_count: int) -> list[int]:
    """Parse "1-3,5,8-" (1-based, inclusive) into 0-based page indices."""
    pages: list[int] = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                start, end = int(a or 1), int(b or page_count)
            else:
                start = end = int(part)
        except ValueError as e:
            raise HTTPException(400, f"Ungültiger Seitenbereich: {part}") from e
        if not (1 <= start <= end <= page_count):
            raise HTTPException(400, f"Seitenbereich {part} außerhalb von 1–{page_count}")
        pages.extend(range(start - 1, end))
    if not pages:
        raise HTTPException(400, "Keine Seiten ausgewählt")
    return pages


def _run(cmd: list[str], timeout: int, what: str) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise HTTPException(504, f"{what} hat zu lange gedauert") from e
    if proc.returncode != 0:
        raise HTTPException(422, f"{what} fehlgeschlagen: {proc.stderr.decode(errors='replace')[-300:]}")


@router.post("/merge")
def merge(files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Mindestens zwei PDFs auswählen")
    wd = new_workdir()
    writer = PdfWriter()
    for f in files:
        for page in _reader(save_upload(f, wd, {"pdf"})).pages:
            writer.add_page(page)
    out = wd / "zusammengefuehrt.pdf"
    writer.write(out)
    return send_and_cleanup(out, wd)


@router.post("/split")
def split(file: UploadFile = File(...), ranges: str = Form("")):
    """With ranges: one PDF containing those pages. Without: a ZIP with one PDF per page."""
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    reader = _reader(src)
    stem = src.stem
    if ranges.strip():
        writer = PdfWriter()
        for i in parse_ranges(ranges, len(reader.pages)):
            writer.add_page(reader.pages[i])
        out = wd / f"{stem}_auszug.pdf"
        writer.write(out)
        return send_and_cleanup(out, wd)
    parts = []
    for i, page in enumerate(reader.pages, 1):
        writer = PdfWriter()
        writer.add_page(page)
        p = wd / f"{stem}_seite_{i:03d}.pdf"
        writer.write(p)
        parts.append(p)
    return send_and_cleanup(zip_files(parts, wd / f"{stem}_seiten.zip"), wd)


@router.post("/compress")
def compress(file: UploadFile = File(...), level: str = Form("ebook")):
    if level not in ("screen", "ebook", "printer"):
        raise HTTPException(400, "level muss screen, ebook oder printer sein")
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    _reader(src)
    out = wd / f"{src.stem}_komprimiert.pdf"
    _run(
        ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", f"-dPDFSETTINGS=/{level}",
         "-dNOPAUSE", "-dBATCH", "-dQUIET", "-dSAFER", f"-sOutputFile={out}", str(src)],
        300, "Komprimieren",
    )
    # Ghostscript can make already-optimised files larger; keep the smaller one.
    if out.stat().st_size >= src.stat().st_size:
        out.unlink()
        src.rename(out)
    return send_and_cleanup(out, wd)


@router.post("/rotate")
def rotate(file: UploadFile = File(...), angle: int = Form(90), ranges: str = Form("")):
    if angle not in (90, 180, 270):
        raise HTTPException(400, "Winkel muss 90, 180 oder 270 sein")
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    reader = _reader(src)
    targets = set(parse_ranges(ranges, len(reader.pages))) if ranges.strip() else set(range(len(reader.pages)))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        writer.add_page(page)
        if i in targets:
            writer.pages[i].rotate(angle)
    out = wd / f"{src.stem}_gedreht.pdf"
    writer.write(out)
    return send_and_cleanup(out, wd)


@router.post("/protect")
def protect(file: UploadFile = File(...), password: str = Form(...)):
    if len(password) < 1:
        raise HTTPException(400, "Passwort fehlt")
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    writer = PdfWriter(clone_from=_reader(src))
    writer.encrypt(user_password=password, owner_password=None, algorithm="AES-256")
    out = wd / f"{src.stem}_geschuetzt.pdf"
    writer.write(out)
    return send_and_cleanup(out, wd)


@router.post("/unlock")
def unlock(file: UploadFile = File(...), password: str = Form("")):
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    writer = PdfWriter(clone_from=_reader(src, password))
    out = wd / f"{src.stem}_entsperrt.pdf"
    writer.write(out)
    return send_and_cleanup(out, wd)


@router.post("/to-images")
def to_images(file: UploadFile = File(...), format: str = Form("png"), dpi: int = Form(150)):
    if format not in ("png", "jpg"):
        raise HTTPException(400, "Format muss png oder jpg sein")
    if not 50 <= dpi <= 600:
        raise HTTPException(400, "DPI muss zwischen 50 und 600 liegen")
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    _reader(src)
    outdir = wd / "out"
    outdir.mkdir()
    flag = "-png" if format == "png" else "-jpeg"
    _run(["pdftoppm", flag, "-r", str(dpi), str(src), str(outdir / src.stem)], 300, "PDF → Bilder")
    images = sorted(outdir.iterdir())
    if len(images) == 1:
        return send_and_cleanup(images[0], wd)
    return send_and_cleanup(zip_files(images, wd / f"{src.stem}_bilder.zip"), wd)


@router.post("/to-text")
def to_text(file: UploadFile = File(...)):
    wd = new_workdir()
    src = save_upload(file, wd, {"pdf"})
    _reader(src)
    out = wd / f"{src.stem}.txt"
    _run(["pdftotext", "-layout", "-enc", "UTF-8", str(src), str(out)], 120, "PDF → Text")
    return send_and_cleanup(out, wd, media_type="text/plain; charset=utf-8")


@router.post("/from-images")
def from_images(files: list[UploadFile] = File(...)):
    wd = new_workdir()
    pages = []
    for f in files:
        try:
            img = Image.open(save_upload(f, wd, IMAGE_EXT))
            img.load()
        except (OSError, Image.DecompressionBombError) as e:
            raise HTTPException(400, f"{f.filename}: kein gültiges Bild") from e
        pages.append(img.convert("RGB"))
    out = wd / "bilder.pdf"
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return send_and_cleanup(out, wd)


@router.post("/from-office")
def from_office(file: UploadFile = File(...)):
    wd = new_workdir()
    src = save_upload(file, wd, OFFICE_EXT)
    # A private profile per call lets several conversions run in parallel.
    profile = wd / f"lo-{uuid.uuid4().hex}"
    _run(
        ["soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--norestore",
         "--convert-to", "pdf", "--outdir", str(wd / "out"), str(src)],
        settings.OFFICE_TIMEOUT_S, "Office → PDF",
    )
    out = wd / "out" / f"{src.stem}.pdf"
    if not out.exists():
        raise HTTPException(422, "Office → PDF fehlgeschlagen")
    return send_and_cleanup(out, wd, filename=safe_name(out.name))
