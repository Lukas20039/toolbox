import httpx
import pytest


@pytest.fixture
def api(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as client:
        yield client


def test_health(api):
    assert api.get("/api/health").json() == {"status": "ok"}


def test_config(api):
    cfg = api.get("/api/config").json()
    assert cfg["maxUploadMb"] > 0
    assert isinstance(cfg["allowedMediaHosts"], list)


def test_unknown_job(api):
    assert api.get("/api/jobs/doesnotexist").status_code == 404
    assert api.get("/api/jobs/doesnotexist/file").status_code == 404


def test_merge_needs_two_files(api, files):
    with files["pdf2"].open("rb") as fh:
        res = api.post("/api/pdf/merge", files=[("files", ("a.pdf", fh, "application/pdf"))])
    assert res.status_code == 400


def test_corrupt_pdf(api):
    res = api.post("/api/pdf/to-text", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert res.status_code == 400


def test_path_traversal_filename_is_sanitised(api, files):
    with files["pdf2"].open("rb") as fh:
        res = api.post("/api/pdf/rotate", files={"file": ("../../etc/evil.pdf", fh, "application/pdf")})
    assert res.status_code == 200
    assert "evil_gedreht.pdf" in res.headers["content-disposition"]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://youtube.com/x", "http://localhost.evil.com/x"])
def test_download_rejects_bad_urls(api, url):
    res = api.post("/api/media/download", data={"url": url, "format": "mp3"})
    assert res.status_code == 400
