"""Загрузить подготовленный корпус из data/demo_sources.json и веса моделей.

Никаких синтетических транскриптов или подставных результатов распознавания.
"""
import argparse
from pathlib import Path
import sys

from video_lab.common import ROOT, read_json, save_json
from video_lab.media import acquire, ffmpeg, probe


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", action="store_true", help="Также скачать YOLOv8n и Whisper base")
    args = parser.parse_args()
    sources = read_json(ROOT / "data" / "demo_sources.json")
    local = []
    for item in sources:
        name = item.get("name", Path(item["source"]).stem)
        media, receipt = acquire(item["source"], ROOT / "data" / "demo" / name)
        if item.get("clip_seconds"):
            clip = media.parent / "clip.mp4"
            target_duration = min(float(item["clip_seconds"]), probe(media)["duration"])
            if not clip.exists() or abs(probe(clip)["duration"] - target_duration) > 0.15:
                ffmpeg("-i", media, "-t", item["clip_seconds"], "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", clip)
            media = clip
        local.append({**item, "source": media.relative_to(ROOT / "data").as_posix(),
                      "origin_url": item["source"]})
        print(f"{name}: {media.stat().st_size:,} bytes; original_sha256={receipt['sha256']}", flush=True)
    save_json(ROOT / "data" / "demo_local.json", local)
    if args.models:
        from video_lab.pipeline import Models
        import numpy as np
        models = Models()
        models.detect(np.zeros((64, 64, 3), dtype=np.uint8), 0.4)
        models.transcribe(np.zeros(16000, dtype=np.float32), "en")
    print("Демо подготовлено. python lab6.py run --manifest data/demo_local.json", flush=True)


if __name__ == "__main__":
    main()
