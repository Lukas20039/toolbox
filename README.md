# 🧰 Toolbox

Selbst gehostete Sammlung nützlicher Datei-Konverter und Werkzeuge – eine Web-Oberfläche, ein Docker-Container.

## Funktionen

**Datei-Konverter (serverseitig)**

| Bereich | Tools |
|---|---|
| Video / Audio | YouTube, Vimeo, SoundCloud & Co. → MP3 / M4A / Opus / WAV / FLAC / MP4 / WebM · Datei-Konvertierung (z. B. MP4 → MP3, MOV → MP4, Video → GIF) |
| PDF | Zusammenführen · Teilen / Seiten extrahieren · Komprimieren · Drehen · Passwort setzen / entfernen · PDF → Bilder · PDF → Text · Bilder → PDF · Word / Excel / PowerPoint → PDF |
| Bilder | PNG / JPG / WebP / GIF / BMP / TIFF / ICO konvertieren und skalieren |

**Werkzeuge im Browser (laufen rein clientseitig)**

JSON-Formatter · Base64 · URL-Encode · SHA-Hashes · UUID · Passwort-Generator · Unix-Timestamp · Text-Zähler · Text umwandeln (camelCase, snake_case, …) · Regex-Tester · Farb-Konverter · Zahlensysteme · Prozentrechner · JWT-Decoder · Text-Vergleich · Lorem Ipsum

## Starten

```bash
docker run -d -p 8000:8000 --tmpfs /tmp:size=4g,mode=1777 ghcr.io/lukas20039/toolbox:latest
```

oder mit `docker compose up -d`. Danach läuft die Oberfläche auf <http://localhost:8000>, die API-Doku auf <http://localhost:8000/api/docs>.

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| `PORT` | `8000` | HTTP-Port |
| `MAX_UPLOAD_MB` | `200` | Maximale Upload-Größe pro Datei |
| `MAX_DOWNLOAD_MB` | `2000` | Maximale Größe von URL-Downloads |
| `MAX_MEDIA_DURATION_MIN` | `180` | Maximale Video-Länge bei URL-Downloads |
| `MAX_CONCURRENT_JOBS` | `2` | Gleichzeitige Download-/Konvertier-Jobs |
| `JOB_TTL_MIN` | `60` | Nach dieser Zeit werden Ergebnisse und Uploads gelöscht |
| `ALLOWED_MEDIA_HOSTS` | YouTube, Vimeo, SoundCloud, … | Kommagetrennte Domains für URL-Downloads, `*` = alle |
| `ENABLE_URL_DOWNLOAD` | `true` | URL-Downloads komplett abschalten |

Jobs werden im Speicher gehalten – die App läuft deshalb als **ein** Prozess. Für mehr Last mehrere Container hinter einen Load-Balancer mit Sticky Sessions stellen.

## Öffentlich betreiben

- `ALLOWED_MEDIA_HOSTS` nicht auf `*` setzen: Der Downloader würde sonst beliebige Adressen abrufen, auch interne (SSRF).
- Die App hat keine Authentifizierung und kein Rate-Limit. Bei öffentlichem Betrieb einen Reverse-Proxy davor setzen (z. B. Caddy/Traefik mit Rate-Limit oder Basic-Auth).
- YouTube sperrt Rechenzentrums-IPs häufig. Wenn Downloads mit „Sign in to confirm you're not a bot“ scheitern, liegt es an der IP des Servers, nicht an der App.
- Nutzer dürfen nur Inhalte herunterladen, an denen sie die Rechte haben oder deren Lizenz das erlaubt. Die Nutzungsbedingungen der jeweiligen Plattform gelten.

## Entwicklung

```bash
docker build -t toolbox:dev .
docker run --rm --network host -e ALLOWED_MEDIA_HOSTS=127.0.0.1,localhost toolbox:dev

# zweites Terminal: E2E-Tests (Playwright) gegen den laufenden Container
pip install -r requirements-dev.txt && playwright install chromium
BASE_URL=http://127.0.0.1:8000 pytest -v
```

Die URL-Download-Tests starten einen lokalen HTTP-Server mit einem Testvideo; der Container muss ihn über `--network host` erreichen. Echte YouTube-Downloads testet `RUN_YOUTUBE=1 pytest tests/e2e/test_youtube.py`.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): baut das Docker-Image, startet es und führt alle E2E-Tests mit Playwright aus. Auf `main` und bei Tags `v*` wird das Image danach nach `ghcr.io/lukas20039/toolbox` gepusht (`latest`, Version, Commit-SHA).
- **YouTube smoke test**: läuft wöchentlich und prüft echte YouTube-Downloads. Er blockiert die CI nicht, weil YouTube CI-Runner oft sperrt.
- **Dependabot** hält yt-dlp, Basis-Images und Actions aktuell.

## Lizenz

[MIT](LICENSE). Das Docker-Image enthält zusätzlich Programme unter eigenen Lizenzen (FFmpeg, Ghostscript, Poppler, LibreOffice, yt-dlp, Deno); sie werden als eigenständige Programme aufgerufen.
