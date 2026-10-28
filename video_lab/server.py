from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .common import ROOT, read_json
from .semantics import search


def create_app(results: Path):
    results = results.resolve()
    index = read_json(results / "index.json")
    videos = {v["id"]: v for v in index["videos"]}
    app = FastAPI(title="Видеоархив — лабораторная №6", version="1.0")

    def get_video(video_id):
        if video_id not in videos:
            raise HTTPException(404, "Ролик не найден")
        return videos[video_id]

    def safe_file(path):
        resolved = (results / path).resolve()
        if not resolved.is_relative_to(results) or not resolved.is_file():
            raise HTTPException(404, "Файл не найден")
        return resolved

    @app.get("/")
    def home():
        return FileResponse(ROOT / "video_lab" / "interface.html")

    @app.get("/api/videos")
    def list_videos():
        return [{key: v[key] for key in ("id", "title", "duration", "interval", "cluster", "topic_words", "warnings")}
                for v in videos.values()]

    @app.get("/api/videos/{video_id}")
    def detail(video_id: str):
        v = get_video(video_id)
        return {key: v[key] for key in ("id", "title", "duration", "interval", "events", "entities", "segments", "technical", "warnings")}

    @app.get("/api/topics")
    def topics():
        return index["topics"]

    @app.get("/api/search")
    def find(q: str = Query(default="", max_length=200), kind: str = "all", limit: int = Query(default=200, ge=1, le=1000)):
        if kind not in {"all", "object", "speech", "scene", "audio"}:
            raise HTTPException(422, "Неизвестный тип события")
        return search(index, q, kind, limit)

    @app.get("/media/{video_id}")
    def media(video_id: str):
        return FileResponse(safe_file(get_video(video_id)["media"]), media_type="video/mp4")

    @app.get("/frame/{video_id}/{event_id}")
    def frame(video_id: str, event_id: str):
        event = next((e for e in get_video(video_id)["events"] if e["id"] == event_id), None)
        if not event or not event.get("frame"):
            raise HTTPException(404, "У события нет кадра")
        return FileResponse(safe_file(event["frame"]), media_type="image/jpeg")

    return app
