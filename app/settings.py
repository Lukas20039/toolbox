"""Runtime configuration, read from environment variables."""

import os
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


DEFAULT_MEDIA_HOSTS = (
    "youtube.com,youtu.be,youtube-nocookie.com,vimeo.com,soundcloud.com,"
    "dailymotion.com,twitch.tv,bandcamp.com,archive.org"
)

WORK_DIR = Path(os.environ.get("WORK_DIR", "/tmp/toolbox"))
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 200)
MAX_DOWNLOAD_MB = _int("MAX_DOWNLOAD_MB", 2000)
MAX_MEDIA_DURATION_MIN =_int("MAX_MEDIA_DURATION_MIN", 180)
MAX_CONCURRENT_JOBS = _int("MAX_CONCURRENT_JOBS", 2)
JOB_TTL_MIN = _int("JOB_TTL_MIN", 60)
OFFICE_TIMEOUT_S = _int("OFFICE_TIMEOUT_S", 120)

# Comma-separated host list for URL downloads; "*" allows every host.
# Restricting hosts prevents the downloader from being abused to fetch
# internal addresses (SSRF) when the service is publicly reachable.
ALLOWED_MEDIA_HOSTS = [
    h.strip().lower()
    for h in os.environ.get("ALLOWED_MEDIA_HOSTS", DEFAULT_MEDIA_HOSTS).split(",")
    if h.strip()
]
ENABLE_URL_DOWNLOAD = os.environ.get("ENABLE_URL_DOWNLOAD", "true").lower() == "true"

WORK_DIR.mkdir(parents=True, exist_ok=True)
