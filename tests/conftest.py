"""Shared fixtures for the end-to-end tests.

The tests drive a running Toolbox instance (normally the Docker container)
through a real browser. Point them at it with BASE_URL.
"""

import functools
import os
import threading
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, base_url):
    return {**browser_context_args, "base_url": base_url, "accept_downloads": True}


def make_text_pdf(path: Path, pages: int, label: str = "Toolbox") -> Path:
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for i in range(1, pages + 1):
        page = writer.add_blank_page(595, 842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 24 Tf 72 720 Td ({label} Seite {i}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(path)
    return path


def make_png(path: Path, size=(200, 100), color="tomato") -> Path:
    img = Image.new("RGBA", size, color)
    ImageDraw.Draw(img).rectangle((10, 10, 60, 60), fill=(0, 0, 0, 0))
    img.save(path)
    return path


def make_docx(path: Path, text: str) -> Path:
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
        ),
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


@pytest.fixture(scope="session")
def files(tmp_path_factory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("inputs")
    return {
        "pdf3": make_text_pdf(d / "drei.pdf", 3),
        "pdf2": make_text_pdf(d / "zwei.pdf", 2, "Zweites"),
        "png_a": make_png(d / "a.png"),
        "png_b": make_png(d / "b.png", (100, 200), "steelblue"),
        "docx": make_docx(d / "brief.docx", "Hallo aus Word"),
        "mp4": FIXTURES / "sample.mp4",
    }


@pytest.fixture(scope="session")
def media_server() -> str:
    """Serve the fixtures over HTTP so the URL downloader can fetch them.

    The app container must share the host network (docker run --network host)
    and allow 127.0.0.1 via ALLOWED_MEDIA_HOSTS.
    """
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(FIXTURES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
