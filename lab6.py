"""Лабораторная №6 — обработка, анализ и поиск видео."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from video_lab.common import ROOT, clock, read_json


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Ожидается положительное конечное число")
    return result


def probability(value):
    number = positive(value)
    if number > 1:
        raise argparse.ArgumentTypeError("Порог должен быть в (0, 1]")
    return number


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    process = sub.add_parser("run", help="Обработать список URL/файлов")
    inputs = process.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--manifest", type=Path, help="JSON: список source/title/language/interval")
    inputs.add_argument("--input", nargs="+", help="Один или несколько URL/путей")
    process.add_argument("--output", type=Path, default=None,
                         help="Папка результатов; автоматически: демо → results, файлы → results_my, URL → results_youtube")
    process.add_argument("--interval", type=positive, default=None, help="Шаг кадров в секундах; по умолчанию авто")
    process.add_argument("--confidence", type=probability, default=0.4)
    process.add_argument("--scene-threshold", type=probability, default=0.45)
    process.add_argument("--yolo", default="yolov8n.pt")
    process.add_argument("--whisper", default="base", choices=["tiny", "base", "small", "medium", "large", "turbo"])
    process.add_argument("--language", default=None, help="ru/en; по умолчанию авто, manifest имеет приоритет")
    process.add_argument("--device", default="cpu")
    process.add_argument("--force", action="store_true", help="Пересчитать анализ")
    serve = sub.add_parser("serve", help="Локальный интерфейс и FastAPI")
    serve.add_argument("--results", type=Path, default=ROOT / "results")
    serve.add_argument("--port", type=int, default=8006)
    query = sub.add_parser("search", help="Поиск по событиям из консоли")
    query.add_argument("query")
    query.add_argument("--results", type=Path, default=ROOT / "results")
    query.add_argument("--type", choices=["all", "speech", "object", "scene", "audio"], default="all")
    check = sub.add_parser("verify", help="Проверить целостность результатов")
    check.add_argument("--results", type=Path, default=ROOT / "results")
    check.add_argument("--minimum-videos", type=int, default=5)
    args = parser.parse_args()
    if args.command == "run":
        from video_lab.pipeline import run
        if args.manifest:
            items = read_json(args.manifest)
            base = args.manifest.resolve().parent
        else:
            items = [{"source": source} for source in args.input]
            base = Path.cwd()
        if not isinstance(items, list) or not items:
            parser.error("Манифест должен содержать непустой список")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("source"), str):
                parser.error("Каждая запись должна содержать строку source")
            if not item["source"].startswith(("http://", "https://")):
                item["source"] = str((base / item["source"]).resolve())
        config = {key: getattr(args, key) for key in
                  ("interval", "confidence", "scene_threshold", "yolo", "whisper", "language", "device")}
        from video_lab.output import result_directory
        output = result_directory(items, args.manifest, args.output)
        print(f"Папка результатов: {output}", flush=True)
        index = run(items, output, config, args.force)
        return 1 if index["failures"] or not index["videos"] else 0
    if args.command == "serve":
        import uvicorn
        from video_lab.server import create_app
        uvicorn.run(create_app(args.results.resolve()), host="127.0.0.1", port=args.port)
    elif args.command == "search":
        from video_lab.semantics import search
        matches = search(read_json(args.results / "index.json"), args.query, args.type)
        for hit in matches:
            print(f"{hit['title']} | {clock(hit['start'])}–{clock(hit['end'])} | {hit['type']} | {hit['label']}")
            print(f"  http://127.0.0.1:8006/?video={hit['video_id']}&t={hit['start']}")
        print(f"Найдено: {len(matches)}")
    elif args.command == "verify":
        from video_lab.validation import verify
        checks = verify(args.results.resolve(), args.minimum_videos)
        for message in checks:
            print(message)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        raise SystemExit(1)
