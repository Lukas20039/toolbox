"""Audio/video endpoints: URL download (yt-dlp) and file conversion (ffmpeg)."""

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import jobs, settings
from .files import new_workdir, save_upload
from .jobs import Job, JobError

router = APIRouter(prefix="/api", tags=["media"])

MEDIA_EXT = {
    "mp4", "mkv", "mov", "avi", "webm", "flv", "wmv", "m4v", "3gp", "mpeg", "mpg",
    "mp3", "wav", "ogg", "oga", "opus", "flac", "m4a", "aac", "wma", "aiff",
}
AUDIO_ONLY = {"mp3", "m4a", "wav", "ogg", "flac", "opus"}

FFMPEG_ARGS: dict[str, list[str]] = {
    "mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "wav": ["-vn", "-c:a", "pcm_s16le"],
    "ogg": ["-vn", "-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-vn", "-c:a", "libopus", "-b:a", "128k"],
    "flac": ["-vn", "-c:a", "flac"],
    "mp4": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-deadline", "realtime",
             "-cpu-used", "8", "-c:a", "libopus", "-b:a", "128k"],
    "gif": ["-an", "-vf", "fps=12,scale='min(480,iw)':-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"],
}

DOWNLOAD_FORMATS = {"mp3", "m4a", "wav", "flac", "opus", "mp4", "webm"}
VIDEO_QUALITIES = {"2160", "1440", "1080", "720", "480", "360"}


def _probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, check=False,
        ).stdout.strip()
        return float(out)
    except (ValueError, subprocess.TimeoutExpired):
        return None


def _ffmpeg(src: Path, dest: Path, fmt: str, job: Job) -> None:
    duration = _probe_duration(src)
    if duration is None:
        raise JobError("Datei enthält keine lesbaren Audio-/Videodaten")
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(src), *FFMPEG_ARGS[fmt],
           "-progress", "pipe:1", "-nostats", str(dest)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout
    for line in proc.stdout:
        m = re.match(r"out_time_us=(\d+)", line)
        if m and duration:
            job.progress = min(99.0, int(m.group(1)) / 1e6 / duration * 100)
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0 or not dest.exists():
        tail = stderr.strip().splitlines()[-1:] or ["unbekannter Fehler"]
        raise JobError(f"Konvertierung fehlgeschlagen: {tail[0][:200]}")


@router.post("/media/convert")
def convert(file: UploadFile = File(...), format: str = Form("mp3")):
    if format not in FFMPEG_ARGS:
        raise HTTPException(400, f"Zielformat muss eines von {', '.join(FFMPEG_ARGS)} sein")
    wd = new_workdir()
    src = save_upload(file, wd, MEDIA_EXT)
    dest_dir = wd / "out"
    dest_dir.mkdir()
    dest = dest_dir / f"{src.stem}.{format}"

    def work(job: Job) -> Path:
        job.message = "Konvertiere…"
        _ffmpeg(src, dest, format, job)
        return dest

    return jobs.submit("convert", work, wd).public()


def host_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if "*" in settings.ALLOWED_MEDIA_HOSTS:
        return True
    host = parsed.hostname.lower()
    return any(host == h or host.endswith("." + h) for h in settings.ALLOWED_MEDIA_HOSTS)


def _ydl_options(fmt: str, quality: str, outdir: Path, job: Job) -> dict:
    def hook(d: dict) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                # Downloading is ~90 % of the work; post-processing gets the rest.
                job.progress = min(90.0, d.get("downloaded_bytes", 0) / total * 90)
            job.message = "Lade herunter…"
        elif d.get("status") == "finished":
            job.message = "Verarbeite…"
            job.progress = max(job.progress, 90.0)

    max_dur = settings.MAX_MEDIA_DURATION_MIN * 60

    def match_filter(info: dict, *, incomplete: bool = False) -> str | None:
        dur = info.get("duration")
        if dur and dur > max_dur:
            return f"Video ist länger als {settings.MAX_MEDIA_DURATION_MIN} Minuten"
        return None

    opts: dict = {
        "outtmpl": str(outdir / "%(title).80B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
        "match_filter": match_filter,
        "max_filesize": settings.MAX_DOWNLOAD_MB * 1024 * 1024,
        "socket_timeout": 30,
        "retries": 3,
        "windowsfilenames": True,
    }
    if fmt in AUDIO_ONLY:
        opts["format"] = "bestaudio/best"
        pp: dict = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
        if fmt == "mp3":
            pp["preferredquality"] = "192"
        opts["postprocessors"] = [pp]
    else:
        h = quality if quality in VIDEO_QUALITIES else "1080"
        if fmt == "mp4":
            opts["format"] = (
                f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}][ext=mp4]/"
                f"bv*[height<={h}]+ba/b[height<={h}]/b"
            )
        else:
            opts["format"] = f"bv*[height<={h}][ext=webm]+ba[ext=webm]/bv*[height<={h}]+ba/b[height<={h}]/b"
        opts["merge_output_format"] = fmt
        # Re-encode only if the container still doesn't match after merging.
        opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": fmt}]
    return opts


@router.post("/media/download")
def download(url: str = Form(...), format: str = Form("mp3"), quality: str = Form("1080")):
    if not settings.ENABLE_URL_DOWNLOAD:
        raise HTTPException(403, "URL-Downloads sind auf diesem Server deaktiviert")
    url = url.strip()
    if format not in DOWNLOAD_FORMATS:
        raise HTTPException(400, f"Format muss eines von {', '.join(sorted(DOWNLOAD_FORMATS))} sein")
    if not host_allowed(url):
        raise HTTPException(400, "Diese Adresse ist nicht erlaubt. Unterstützt: " + ", ".join(settings.ALLOWED_MEDIA_HOSTS))

    def work(job: Job) -> Path:
        import yt_dlp  # imported lazily: slow import, only needed here

        outdir = job.workdir / "out"
        outdir.mkdir(exist_ok=True)
        job.message = "Starte…"
        try:
            with yt_dlp.YoutubeDL(_ydl_options(format, quality, outdir, job)) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
            raise JobError(f"Download fehlgeschlagen: {msg[:300]}") from e
        files = [p for p in outdir.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
        if not files:
            raise JobError("Download übersprungen (z. B. zu lang oder zu groß)")
        return max(files, key=lambda p: p.stat().st_size)

    return jobs.submit("download", work).public()


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job nicht gefunden oder abgelaufen")
    return job.public()


@router.get("/jobs/{job_id}/file")
def job_file(job_id: str):
    job = jobs.get(job_id)
    if not job or job.status != "done" or not job.result or not job.result.exists():
        raise HTTPException(404, "Datei nicht verfügbar")
    # Kept until the job expires so the download can be retried.
    return FileResponse(job.result, filename=job.result.name)
