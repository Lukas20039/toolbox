from playwright.sync_api import expect


def test_json_formatter(page):
    page.goto("/")
    format_button = page.locator("#json-in ~ .row").get_by_role("button", name="Formatieren")
    page.fill("#json-in", '{"a":1,"b":[true]}')
    format_button.click()
    expect(page.locator("#json-out")).to_have_text('{\n  "a": 1,\n  "b": [\n    true\n  ]\n}')
    page.fill("#json-in", "{kaputt")
    format_button.click()
    expect(page.locator("#json-out")).to_contain_text("❌")


def test_base64_roundtrip_with_umlauts(page):
    page.goto("/")
    page.fill("#b64-in", "Grüße")
    page.locator("#b64-in ~ .row").get_by_role("button", name="Encode").click()
    expect(page.locator("#b64-out")).to_have_text("R3LDvMOfZQ==")


def test_sha256(page):
    page.goto("/")
    page.fill("#hash-in", "abc")
    expect(page.locator("#hash-out")).to_contain_text(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_search_filters_tools(page):
    page.goto("/")
    page.fill("#search", "youtube")
    expect(page.locator(".tool:visible")).to_have_count(1)
    expect(page.locator(".tool:visible h2")).to_contain_text("YouTube")
    page.fill("#search", "")
    expect(page.locator(".tool:visible")).not_to_have_count(1)
