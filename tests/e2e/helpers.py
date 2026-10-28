from pathlib import Path

from playwright.sync_api import Locator, Page, expect


def tool(page: Page, testid: str) -> Locator:
    page.goto("/")
    form = page.locator(f'form[data-testid="{testid}"]')
    expect(form.locator("button[type=submit]")).to_be_enabled()
    return form


def submit_and_download(page: Page, form: Locator, dest_dir: Path, timeout: float = 60_000) -> Path:
    with page.expect_download(timeout=timeout) as info:
        form.locator("button[type=submit]").click()
    download = info.value
    path = dest_dir / download.suggested_filename
    download.save_as(path)
    return path


def submit_expect_error(page: Page, form: Locator, contains: str, timeout: float = 30_000) -> None:
    form.locator("button[type=submit]").click()
    error = form.locator("xpath=..").locator('[data-testid="error"]')
    expect(error).to_contain_text(contains, timeout=timeout)
