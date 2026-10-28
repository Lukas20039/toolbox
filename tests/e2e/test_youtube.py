"""Real YouTube downloads.

Skipped unless RUN_YOUTUBE=1: YouTube often blocks CI runner IPs, so this runs
in a separate, non-blocking workflow to detect when yt-dlp needs an update.
"""

import os

import pytest
from helpers import submit_and_download, tool
from test_media import is_mp3, is_mp4

pytestmark = pytest.mark.skipif(os.environ.get("RUN_YOUTUBE") != "1", reason="RUN_YOUTUBE=1 not set")

# "Me at the zoo" – the first YouTube video, 19 seconds long.
VIDEO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.mark.parametrize("fmt,check", [("mp3", is_mp3), ("mp4", is_mp4)])
def test_youtube_download(page, tmp_path, fmt, check):
    form = tool(page, "media-download")
    form.locator("input[name=url]").fill(VIDEO)
    form.locator("select[name=format]").select_option(fmt)
    form.locator("select[name=quality]").select_option("360")
    out = submit_and_download(page, form, tmp_path, timeout=180_000)
    assert out.suffix == f".{fmt}"
    assert check(out.read_bytes())
