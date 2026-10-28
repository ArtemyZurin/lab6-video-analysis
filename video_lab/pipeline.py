from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .common import ROOT, read_json, relative, save_json, sha256
from .events import build_events, entity_statistics
from .media import acquire, audio_features, choose_interval, extract_audio, playable_copy, probe, sampled_frames
from .semantics import group_videos
from .transcripts import clean_segments

LOG = logging.getLogger("lab6")
PIPELINE_VERSION = 2


class Models:
    def __init__(self, yolo="yolov8n.pt", whisper="base", device="cpu"):
        self.yolo_name, self.whisper_name, self.device = yolo, whisper, device
        self.detector = self.recognizer = None

    def detect(self, image, confidence):
        if self.detector is None:
            from ultralytics import YOLO
            weights = Path(self.yolo_name)
            if not weights.is_absolute():
                weights = ROOT / "models" / weights
            weights.parent.mkdir(parents=True, exist_ok=True)
            LOG.info("Загрузка YOLO: %s", weights)
            self.detector = YOLO(str(weights))
        return self.detector.predict(image, conf=confidence, imgsz=640, device=self.device, verbose=False)[0]

    def transcribe(self, audio, language):
        if self.recognizer is None:
            import torch
            import whisper
            torch.set_num_threads(min(4, torch.get_num_threads()))
            LOG.info("Загрузка Whisper: %s", self.whisper_name)
            self.recognizer = whisper.load_model(self.whisper_name, device=self.device,
                                                download_root=str(ROOT / "models" / "whisper"))
        return self.recognizer.transcribe(audio, language=language, fp16=self.device != "cpu",
                                         verbose=None, temperature=(0, 0.2, 0.4), beam_size=5,
                                         condition_on_previous_text=False, word_timestamps=True,
                                         hallucination_silence_threshold=2.0)


def analyze_frames(media, directory, output, interval, confidence, models):
    import cv2
    directory.mkdir(parents=True, exist_ok=True)
    frames, previous = [], None
    with (directory.parent / "frames.jsonl").open("w", encoding="utf-8") as stream:
        for number, (timestamp, image) in enumerate(sampled_frames(media, interval)):
            hsv = cv2.cvtColor(cv2.resize(image, (160, 90)), cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            distance = float(cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA)) if previous is not None else 0.0
            previous = hist
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            result = models.detect(image, confidence)
            objects = []
            for box in result.boxes:
                objects.append({"label": result.names[int(box.cls.item())],
                                "confidence": float(box.conf.item()),
                                "xyxy": [float(x) for x in box.xyxy[0].tolist()]})
            image_path = directory / f"{number:06d}.jpg"
            # imencode/tofile поддерживает пути с кириллицей на Windows.
            ok, encoded = cv2.imencode(".jpg", result.plot(), [cv2.IMWRITE_JPEG_QUALITY, 82])
            if not ok:
                raise RuntimeError("Не удалось сохранить кадр")
            encoded.tofile(str(image_path))
            row = {"time": round(timestamp, 6), "image": relative(image_path, output), "objects": objects,
                   "brightness": float(gray.mean() / 255), "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                   "scene_distance": distance}
            frames.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    if not frames:
        raise ValueError("Не декодирован ни один кадр")
    return frames


def process_video(item, output, models, config, force=False):
    started = time.monotonic()
    source = item["source"]
    video_id = "v" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    directory = output / "videos" / video_id
    media, metadata = acquire(source, directory)
    technical = probe(media)
    metadata.update({key: item[key] for key in ("title", "description", "tags", "categories", "origin_url", "clip_seconds") if key in item})
    effective = {**config, "language": item.get("language", config["language"]),
                 "interval": item.get("interval", config["interval"])}
    signature = hashlib.sha256(json.dumps({"config": effective, "metadata": metadata,
                               "version": PIPELINE_VERSION}, sort_keys=True).encode()).hexdigest()
    cache = directory / "analysis.json"
    if cache.exists() and not force:
        old = read_json(cache)
        required = [output / old["media"], directory / "frames.jsonl", directory / "transcript.json"]
        if old.get("signature") == signature and all(p.is_file() for p in required) and all(
                (output / f["image"]).is_file() for f in old["frames"]):
            LOG.info("Кэш: %s", metadata["title"])
            return old
    playable = directory / "video.mp4"
    LOG.info("Подготовка видео: %s", metadata["title"])
    playable_copy(media, playable)
    normalized = probe(playable)
    duration = normalized["duration"]
    if effective["interval"] is None:
        interval, sampling = choose_interval(playable, duration)
    else:
        interval, sampling = float(effective["interval"]), {"rule": "explicit interval"}
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Интервал кадров должен быть положительным конечным числом")
    LOG.info("Кадры и YOLO: %.1f с, шаг %.2f с", duration, interval)
    frames = analyze_frames(playable, directory / "frames", output, interval, config["confidence"], models)
    segments, audio, warnings = [], [], []
    audio_threshold, detected_language = None, None
    if normalized["has_audio"]:
        samples = extract_audio(playable, directory / "audio.wav")
        audio, audio_threshold = audio_features(samples, duration)
        if samples.size and float(np.sqrt(np.mean(samples ** 2))) >= 1e-5:
            LOG.info("Whisper: %s", metadata["title"])
            transcript = models.transcribe(samples, effective["language"])
            detected_language = transcript.get("language")
            segments, rejected = clean_segments(transcript.get("segments", []), duration)
            save_json(directory / "rejected_segments.json", rejected)
            if rejected:
                warnings.append(f"asr_quality: {len(rejected)} подозрительных сегментов исключено из поиска; см. rejected_segments.json")
            save_json(directory / "whisper_raw.json", transcript)
        if not segments:
            warnings.append("empty_transcript: речь не распознана; проверьте тишину/музыку/качество аудио")
    else:
        warnings.append("no_audio: в файле отсутствует аудиодорожка")
    save_json(directory / "transcript.json", {"language": detected_language, "segments": segments, "warnings": warnings})
    save_json(directory / "audio_features.json", {"peak_threshold_dbfs": audio_threshold, "windows": audio})
    save_json(directory / "metadata.json", {"source": metadata, "technical": technical, "normalized": normalized})
    events = build_events(frames, segments, audio, duration, config["scene_threshold"])
    video = {"id": video_id, "title": metadata["title"], "source": source,
             "metadata": metadata, "technical": technical, "duration": duration,
             "media": relative(playable, output), "interval": interval, "sampling": sampling,
             "frames": frames, "segments": segments, "audio": audio, "events": events,
             "entities": entity_statistics(frames, events, duration), "warnings": warnings,
             "detected_language": detected_language, "signature": signature,
             "processing_seconds": round(time.monotonic() - started, 3)}
    save_json(cache, video)
    return video


def run(items, output, config, force=False):
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(output / "pipeline.log", encoding="utf-8")], force=True)
    models = Models(config["yolo"], config["whisper"], config["device"])
    videos, failures = [], []
    seen = set()
    for number, item in enumerate(items, 1):
        source = item.get("source", "")
        if source in seen:
            LOG.warning("Повтор источника пропущен: %s", source)
            continue
        seen.add(source)
        LOG.info("[%d/%d] %s", number, len(items), source)
        try:
            if not source:
                raise ValueError("Отсутствует source")
            videos.append(process_video(item, output, models, config, force))
        except Exception as error:
            LOG.exception("Ошибка источника %s", source)
            failures.append({"source": source, "error": f"{type(error).__name__}: {error}"})
        save_json(output / "failures.json", failures)
    topics = group_videos(videos)
    index = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
             "config": config, "videos": videos, "failures": failures, "topics": topics}
    save_json(output / "index.json", index)
    from .reporting import export_results
    export_results(index, output)
    LOG.info("Готово: %d роликов, %d ошибок. %s", len(videos), len(failures), output)
    return index
