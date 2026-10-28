from __future__ import annotations

import json
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np

from .common import ROOT, read_json, save_json, sha256


def ffmpeg(*args):
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *map(str, args)]
    result = subprocess.run(command, capture_output=True, timeout=3600)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3000:])


def download_options(directory: Path):
    options = {
        "outtmpl": str(directory / "original.%(ext)s"), "noplaylist": True,
        # DASH: отдельные видео/аудио; затем единый файл; затем видео без звука.
        "format": "bv+ba/b/bv", "merge_output_format": "mkv",
        "writeinfojson": True, "socket_timeout": 30, "retries": 3, "quiet": True,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "cachedir": str(ROOT / ".cache" / "yt_dlp"),
    }
    runtimes = {name: {"path": executable} for name in ("deno", "node")
                if (executable := shutil.which(name))}
    if runtimes:
        options["js_runtimes"] = runtimes
    return options


def downloaded_file(info, downloader):
    # prepare_filename может содержать расширение до слияния/постобработки.
    candidates = [info.get("filepath")]
    candidates.extend(item.get("filepath") for item in info.get("requested_downloads", []))
    candidates.append(downloader.prepare_filename(info))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("yt-dlp не создал итоговый файл после загрузки/объединения")


def acquire(source: str, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    receipt = directory / "source.json"
    remote = source.startswith(("https://", "http://"))
    if remote and receipt.exists():
        previous = read_json(receipt)
        media = directory / previous["filename"]
        if previous["source"] == source and media.is_file() and sha256(media) == previous["sha256"]:
            return media, previous
    metadata = {}
    if remote:
        import yt_dlp
        with yt_dlp.YoutubeDL(download_options(directory)) as downloader:
            info = downloader.extract_info(source, download=True)
            if not info or info.get("_type") == "playlist":
                raise ValueError("Укажите ссылку на один ролик, не плейлист")
            media = downloaded_file(info, downloader)
            metadata = {key: info.get(key) for key in (
                "title", "description", "tags", "categories", "upload_date", "duration",
                "view_count", "like_count", "comment_count", "webpage_url", "extractor", "id",
                "format_id", "resolution", "vcodec", "acodec")}
    else:
        original = Path(source).resolve(strict=True)
        media = directory / ("original" + original.suffix.lower())
        if receipt.exists() and media.is_file():
            previous = read_json(receipt)
            if previous["source"] == source and previous["sha256"] == sha256(original) == sha256(media):
                return media, previous
        if original != media.resolve() and (not media.exists() or sha256(original) != sha256(media)):
            shutil.copy2(original, media)
        metadata = {"title": original.stem, "description": "", "tags": [], "categories": []}
    metadata.update(source=source, filename=media.name, sha256=sha256(media),
                    collected_at=datetime.now(timezone.utc).isoformat(),
                    source_kind="url" if remote else "local")
    save_json(receipt, metadata)
    return media, metadata


def probe(path: Path):
    """ffprobe при наличии; PyAV использует те же библиотеки libav без установки в PATH."""
    probe_binary = shutil.which("ffprobe")
    raw = None
    if probe_binary:
        result = subprocess.run([probe_binary, "-v", "error", "-show_format", "-show_streams",
                                 "-of", "json", str(path)], capture_output=True, check=True, timeout=60)
        raw = json.loads(result.stdout)
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("Файл не содержит видеопоток")
        video = container.streams.video[0]
        duration = float(container.duration / av.time_base) if container.duration else (
            float(video.duration * video.time_base) if video.duration else 0)
        if duration <= 0 or not video.average_rate:
            raise ValueError("Не удалось определить длительность/fps")
        context = video.codec_context
        return {"duration": duration, "fps": float(video.average_rate),
                "fps_fraction": str(video.average_rate), "width": context.width, "height": context.height,
                "codec": context.name, "pixel_format": context.format.name if context.format else None,
                "container": container.format.name, "bit_rate": container.bit_rate,
                "bytes": path.stat().st_size, "has_audio": bool(container.streams.audio),
                "audio_codec": container.streams.audio[0].codec_context.name if container.streams.audio else None,
                "probe_backend": "ffprobe + PyAV" if raw else "PyAV / libavformat",
                "ffprobe": raw}


def sampled_frames(path: Path, interval: float):
    """Поточное декодирование; PTS нормализуется к началу видеопотока (в том числе VFR)."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        origin = float(stream.start_time * stream.time_base) if stream.start_time is not None else None
        next_sample = 0.0
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            if origin is None:
                origin = float(frame.time)
            time = max(0.0, float(frame.time) - origin)
            if time + 1e-6 < next_sample:
                continue
            yield time, frame.to_ndarray(format="bgr24")
            next_sample = (int((time + 1e-6) / interval) + 1) * interval


def choose_interval(path: Path, duration: float):
    import cv2
    differences, previous = [], None
    for time, image in sampled_frames(path, 0.5):
        small = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (64, 36)).astype(np.float32) / 255
        if previous is not None:
            differences.append(float(np.mean(np.abs(small - previous))))
        previous = small
        if time >= min(8, duration - 0.5):
            break
    motion = float(np.mean(differences)) if differences else 0.0
    interval = 0.5 if motion > 0.07 else (2.0 if duration > 600 else 1.0)
    return interval, {"pilot_seconds": min(8, duration), "mean_frame_difference": motion,
                      "rule": "0.5 s if difference > 0.07; otherwise 2 s for >600 s, else 1 s"}


def extract_audio(media, path):
    # Сначала нормализуется весь файл (video.mp4), поэтому audio/video имеют одну шкалу.
    ffmpeg("-i", media, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", path)
    with wave.open(str(path), "rb") as audio:
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return samples


def audio_features(samples, duration):
    rows = []
    for offset in range(0, len(samples), 16000):
        chunk = samples[offset:offset + 16000]
        start, end = offset / 16000, min(duration, (offset + len(chunk)) / 16000)
        if start >= end:
            break
        db = float(20 * np.log10(max(1e-6, float(np.sqrt(np.mean(chunk ** 2))))))
        rows.append({"start": start, "end": end, "dbfs": db})
    if not rows:
        return [], None
    # Нижняя граница не позволяет объявлять тишину пиками.
    threshold = max(-35.0, float(np.quantile([r["dbfs"] for r in rows], 0.9)))
    for row in rows:
        row["peak"] = row["dbfs"] >= threshold
    return rows, threshold


def playable_copy(media, destination):
    # Единая временная ось, H.264/AAC и faststart для браузера и любых исходных контейнеров.
    ffmpeg("-i", media, "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-af", "aresample=async=1:first_pts=0", "-movflags", "+faststart", destination)
