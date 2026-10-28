from helpers import submit_and_download, tool
from PIL import Image


def test_png_to_jpg_keeps_aspect_ratio(page, files, tmp_path):
    form = tool(page, "image-convert")
    form.locator("input[name=file]").set_input_files(files["png_a"])
    form.locator("select[name=format]").select_option("jpg")
    form.locator("input[name=width]").fill("50")
    out = submit_and_download(page, form, tmp_path)
    img = Image.open(out)
    assert img.format == "JPEG"
    assert img.size == (50, 25)
    # Transparent area is flattened onto white, not black.
    assert min(img.getpixel((6, 6))) > 200


def test_png_to_webp_and_ico(page, files, tmp_path):
    for fmt, pil_name in (("webp", "WEBP"), ("ico", "ICO")):
        form = tool(page, "image-convert")
        form.locator("input[name=file]").set_input_files(files["png_b"])
        form.locator("select[name=format]").select_option(fmt)
        out = submit_and_download(page, form, tmp_path)
        assert out.suffix == f".{fmt}"
        assert Image.open(out).format == pil_name
