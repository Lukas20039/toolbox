"""Image conversion endpoint."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps

from .files import new_workdir, save_upload, send_and_cleanup

router = APIRouter(prefix="/api/image", tags=["image"])

INPUT_EXT = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "ico"}
OUTPUT = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP", "tiff": "TIFF", "ico": "ICO"}


@router.post("/convert")
def convert(
    file: UploadFile = File(...),
    format: str = Form("png"),
    width: int | None = Form(None),
    height: int | None = Form(None),
    quality: int = Form(85),
):
    if format not in OUTPUT:
        raise HTTPException(400, f"Zielformat muss eines von {', '.join(OUTPUT)} sein")
    for v in (width, height):
        if v is not None and not 1 <= v <= 10000:
            raise HTTPException(400, "Breite/Höhe muss zwischen 1 und 10000 liegen")
    wd = new_workdir()
    src = save_upload(file, wd, INPUT_EXT)
    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
    except (OSError, Image.DecompressionBombError) as e:
        raise HTTPException(400, "Kein gültiges Bild") from e

    if width or height:
        w, h = img.size
        if width and height:
            size = (width, height)
        elif width:
            size = (width, max(1, round(h * width / w)))
        else:
            size = (max(1, round(w * height / h)), height)
        img = img.resize(size, Image.LANCZOS)

    if format in ("jpg", "bmp") and img.mode not in ("RGB", "L"):
        # Formats without alpha: flatten onto white instead of black.
        bg = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        img = bg

    out = wd / f"{src.stem}_konvertiert.{format}"
    opts = {"quality": max(1, min(100, quality))} if format in ("jpg", "webp") else {}
    if format == "ico":
        opts["sizes"] = [(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= max(img.size)] or [(16, 16)]
    img.save(out, OUTPUT[format], **opts)
    return send_and_cleanup(out, wd)
