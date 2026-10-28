from helpers import submit_and_download, submit_expect_error, tool


def is_mp3(data: bytes) -> bool:
    return data[:3] == b"ID3" or (data[0] == 0xFF and data[1] & 0xE0 == 0xE0)


def is_mp4(data: bytes) -> bool:
    return data[4:8] == b"ftyp"


def test_convert_video_to_mp3(page, files, tmp_path):
    form = tool(page, "media-convert")
    form.locator("input[name=file]").set_input_files(files["mp4"])
    form.locator("select[name=format]").select_option("mp3")
    out = submit_and_download(page, form, tmp_path)
    assert out.name == "sample.mp3"
    assert is_mp3(out.read_bytes())


def test_convert_video_to_gif(page, files, tmp_path):
    form = tool(page, "media-convert")
    form.locator("input[name=file]").set_input_files(files["mp4"])
    form.locator("select[name=format]").select_option("gif")
    out = submit_and_download(page, form, tmp_path)
    assert out.read_bytes()[:6] == b"GIF89a"


def test_convert_rejects_non_media(page, files):
    form = tool(page, "media-convert")
    form.locator("input[name=file]").set_input_files(files["pdf2"])
    submit_expect_error(page, form, "nicht unterstützt")


def test_download_url_as_mp3(page, media_server, tmp_path):
    form = tool(page, "media-download")
    form.locator("input[name=url]").fill(f"{media_server}/sample.mp4")
    form.locator("select[name=format]").select_option("mp3")
    out = submit_and_download(page, form, tmp_path)
    assert out.suffix == ".mp3"
    assert is_mp3(out.read_bytes())


def test_download_url_as_mp4(page, media_server, tmp_path):
    form = tool(page, "media-download")
    form.locator("input[name=url]").fill(f"{media_server}/sample.mp4")
    form.locator("select[name=format]").select_option("mp4")
    out = submit_and_download(page, form, tmp_path)
    assert out.suffix == ".mp4"
    assert is_mp4(out.read_bytes())


def test_download_rejects_unlisted_host(page):
    form = tool(page, "media-download")
    form.locator("input[name=url]").fill("http://169.254.169.254/latest/meta-data")
    submit_expect_error(page, form, "nicht erlaubt")


def test_download_reports_missing_media(page, media_server):
    form = tool(page, "media-download")
    form.locator("input[name=url]").fill(f"{media_server}/gibt-es-nicht.mp4")
    submit_expect_error(page, form, "Download fehlgeschlagen")
