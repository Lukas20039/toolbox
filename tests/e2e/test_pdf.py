import zipfile

from helpers import submit_and_download, submit_expect_error, tool
from pypdf import PdfReader


def test_merge(page, files, tmp_path):
    form = tool(page, "pdf-merge")
    form.locator("input[name=files]").set_input_files([files["pdf3"], files["pdf2"]])
    out = submit_and_download(page, form, tmp_path)
    reader = PdfReader(out)
    assert len(reader.pages) == 5
    assert "Zweites Seite 1" in reader.pages[3].extract_text()


def test_split_into_single_pages(page, files, tmp_path):
    form = tool(page, "pdf-split")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    out = submit_and_download(page, form, tmp_path)
    assert out.suffix == ".zip"
    with zipfile.ZipFile(out) as zf:
        assert sorted(zf.namelist()) == [f"drei_seite_00{i}.pdf" for i in (1, 2, 3)]


def test_split_with_ranges(page, files, tmp_path):
    form = tool(page, "pdf-split")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    form.locator("input[name=ranges]").fill("1,3")
    reader = PdfReader(submit_and_download(page, form, tmp_path))
    assert [p.extract_text().strip() for p in reader.pages] == ["Toolbox Seite 1", "Toolbox Seite 3"]


def test_split_invalid_range_shows_error(page, files):
    form = tool(page, "pdf-split")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    form.locator("input[name=ranges]").fill("2-9")
    submit_expect_error(page, form, "außerhalb")


def test_compress(page, files, tmp_path):
    form = tool(page, "pdf-compress")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    out = submit_and_download(page, form, tmp_path)
    assert len(PdfReader(out).pages) == 3


def test_rotate_selected_pages(page, files, tmp_path):
    form = tool(page, "pdf-rotate")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    form.locator("select[name=angle]").select_option("180")
    form.locator("input[name=ranges]").fill("2")
    reader = PdfReader(submit_and_download(page, form, tmp_path))
    assert [p.rotation for p in reader.pages] == [0, 180, 0]


def test_protect_and_unlock(page, files, tmp_path):
    form = tool(page, "pdf-protect")
    form.locator("input[name=file]").set_input_files(files["pdf2"])
    form.locator("input[name=password]").fill("geheim123")
    locked = submit_and_download(page, form, tmp_path)
    assert PdfReader(locked).is_encrypted

    form = tool(page, "pdf-unlock")
    form.locator("input[name=file]").set_input_files(locked)
    form.locator("input[name=password]").fill("falsch")
    submit_expect_error(page, form, "Passwort")

    form.locator("input[name=password]").fill("geheim123")
    unlocked = PdfReader(submit_and_download(page, form, tmp_path))
    assert not unlocked.is_encrypted
    assert len(unlocked.pages) == 2


def test_to_images(page, files, tmp_path):
    form = tool(page, "pdf-to-images")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    form.locator("select[name=dpi]").select_option("72")
    out = submit_and_download(page, form, tmp_path)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert len(names) == 3 and all(n.endswith(".png") for n in names)
        assert zf.read(names[0])[:8] == b"\x89PNG\r\n\x1a\n"


def test_to_text(page, files, tmp_path):
    form = tool(page, "pdf-to-text")
    form.locator("input[name=file]").set_input_files(files["pdf3"])
    text = submit_and_download(page, form, tmp_path).read_text()
    assert "Toolbox Seite 1" in text and "Toolbox Seite 3" in text


def test_from_images(page, files, tmp_path):
    form = tool(page, "pdf-from-images")
    form.locator("input[name=files]").set_input_files([files["png_a"], files["png_b"]])
    reader = PdfReader(submit_and_download(page, form, tmp_path))
    assert len(reader.pages) == 2
    # Landscape first, portrait second: order is preserved.
    first, second = (p.mediabox for p in reader.pages)
    assert first.width > first.height and second.height > second.width


def test_from_office(page, files, tmp_path):
    form = tool(page, "pdf-from-office")
    form.locator("input[name=file]").set_input_files(files["docx"])
    out = submit_and_download(page, form, tmp_path, timeout=120_000)
    assert out.name == "brief.pdf"
    assert "Hallo aus Word" in PdfReader(out).pages[0].extract_text()


def test_wrong_file_type_is_rejected(page, files):
    form = tool(page, "pdf-compress")
    form.locator("input[name=file]").set_input_files(files["png_a"])
    submit_expect_error(page, form, "nicht unterstützt")
