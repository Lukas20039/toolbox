import re

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


def test_pizza_dough_neapolitan_fresh_and_dry_yeast(page):
    page.goto("/")
    out = page.locator("#pz-out")
    # Default: Neapolitanisch, 1000 g, 62 %, 2,8 % Salz, 0,25 % frische Germ
    expect(out).to_contain_text(re.compile(r"Mehl\s+606 g"))
    expect(out).to_contain_text(re.compile(r"Wasser\s+376 g"))
    expect(out).to_contain_text(re.compile(r"Salz\s+17,0 g"))
    expect(out).to_contain_text(re.compile(r"Frische Germ\s+1,5 g"))
    expect(out).not_to_contain_text("Öl")
    page.get_by_label("Trockengerm").check()
    # Trockengerm = frische Germ / 3
    expect(out).to_contain_text(re.compile(r"Trockengerm\s+0,51 g"))
    expect(out).to_contain_text("Packerl à 7 g")


def test_pizza_dough_style_hydration_and_amount(page):
    page.goto("/")
    page.select_option("#pz-style", "ny")
    expect(page.locator("#pz-hyd-val")).to_have_text("62 %")
    expect(page.locator("#pz-out")).to_contain_text("Zucker")
    page.select_option("#pz-style", "teglia")
    expect(page.locator("#pz-hyd-val")).to_have_text("78 %")
    expect(page.locator("#pz-out")).not_to_contain_text("Zucker")
    page.fill("#pz-total", "500")
    page.locator("#pz-hyd").fill("70")
    # 500 / (1 + 0,70 + 0,025 + 0,003) = 289,35 g Mehl
    expect(page.locator("#pz-out")).to_contain_text(re.compile(r"Mehl\s+289 g"))
    expect(page.locator("#pz-out")).to_contain_text(re.compile(r"Wasser\s+203 g"))


def test_search_filters_tools(page):
    page.goto("/")
    page.fill("#search", "youtube")
    expect(page.locator(".tool:visible")).to_have_count(1)
    expect(page.locator(".tool:visible h2")).to_contain_text("YouTube")
    page.fill("#search", "")
    expect(page.locator(".tool:visible")).not_to_have_count(1)
