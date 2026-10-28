import copy
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from video_lab.events import build_events, entity_statistics, object_events
from video_lab.media import audio_features, probe, sampled_frames
from video_lab.semantics import group_videos, search
from video_lab.server import create_app


def frame(t, labels):
    return {"time": t, "image": "frame.jpg", "scene_distance": 0,
            "objects": [{"label": label, "confidence": 0.8, "xyxy": [0, 0, 2, 2]} for label in labels]}


def test_object_intervals_do_not_bridge_absence_or_double_count_people():
    frames = [frame(0, ["person", "person"]), frame(0.5, ["person"]), frame(1, []), frame(1.5, ["person"])]
    events = object_events(frames, 2)
    assert [(e["start"], e["end"]) for e in events] == [(0, 1), (1.5, 2)]
    stats = entity_statistics(frames, events, 2)[0]
    assert stats["detections"] == 4
    assert stats["frames"] == 3
    assert stats["max_simultaneous"] == 2
    assert stats["duration_share"] == 0.75


def test_last_sample_is_clipped_to_video_duration():
    events = build_events([frame(0, []), frame(0.96, ["car"])], [], [], 0.99, 0.45)
    assert events[0]["end"] == 0.99


def test_audio_silence_and_peak_intervals():
    silence, threshold = audio_features(np.zeros(32000, dtype=np.float32), 2)
    assert threshold == -35
    assert not any(row["peak"] for row in silence)
    sound = np.concatenate([np.zeros(16000), np.ones(32000) * 0.5, np.zeros(16000)]).astype(np.float32)
    rows, _ = audio_features(sound, 4)
    events = build_events([], [], rows, 4, 0.45)
    assert [(e["start"], e["end"]) for e in events] == [(1, 3)]


def test_russian_morphology_and_object_aliases():
    index = {"videos": [{"id": "v1", "title": "Пример", "events": [
        {"label": "Ремонт на заводе", "type": "speech", "start": 3, "end": 5},
        {"label": "car", "type": "object", "start": 8, "end": 9}]}]}
    assert search(index, "завод")[0]["start"] == 3
    assert search(index, "машины")[0]["start"] == 8
    assert not search(index, "автобус")
    assert not search(index, "машина", "speech")
    assert len(search(index, "", limit=1)) == 1


def test_asr_music_hallucinations_are_flagged_and_retained_for_audit():
    from video_lab.transcripts import clean_segments
    examples = [{"start": i, "end": i + 1, "text": text} for i, text in enumerate(
        ["...", "A" * 100, "Ремонт завода", "Ремонт завода", "ложная речь"])]
    examples[-1]["no_speech_prob"] = 0.9
    accepted, rejected = clean_segments(examples, 5)
    assert [s["text"] for s in accepted] == ["Ремонт завода"]
    assert len(rejected) == 4 and all(r["reason"] for r in rejected)


def video(text):
    return {"id": text, "title": text, "metadata": {}, "events": [], "segments": []}


def test_topic_modelling_empty_single_and_identical_documents():
    assert not group_videos([])["topics"]
    assert group_videos([video("и в на")])["reason"] == "empty vocabulary"
    assert group_videos([video("завод ремонт")])["selected_k"] == 1
    assert group_videos([video("завод ремонт") for _ in range(5)])["selected_k"] == 1


def test_topics_reproducible_and_shares_sum_to_one():
    texts = ["завод ремонт станок", "станок завод цех", "программа код python", "python код функция", "ремонт цех завод"]
    a, b = [video(s) for s in texts], [video(s) for s in texts]
    first, second = group_videos(a), group_videos(b)
    assert first == second
    assert sum(t["share"] for t in first["topics"]) == pytest.approx(1)
    assert [v["cluster"] for v in a] == [v["cluster"] for v in b]


@pytest.fixture
def tiny_video(tmp_path):
    import av
    path = tmp_path / "проверка видео.mp4"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(12):
            image = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i * 10, dtype=np.uint8), format="rgb24")
            for packet in stream.encode(image):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_real_decode_cyrillic_path_and_sampling(tiny_video):
    info = probe(tiny_video)
    assert info["fps"] == 10
    assert not info["has_audio"]
    assert [round(t, 2) for t, _ in sampled_frames(tiny_video, 0.5)] == [0, 0.5, 1.0]


def test_http_media_range_unknown_video_and_invalid_type(tmp_path):
    (tmp_path / "video.mp4").write_bytes(b"0123456789")
    data = {"videos": [{"id": "v1", "title": "x", "duration": 1, "interval": 1, "cluster": 0,
                         "topic_words": [], "warnings": [], "media": "video.mp4", "events": [],
                         "segments": [], "technical": {}, "entities": []}], "topics": {"topics": []}}
    (tmp_path / "index.json").write_text(json.dumps(data), encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    response = client.get("/media/v1", headers={"Range": "bytes=2-5"})
    assert response.status_code == 206 and response.content == b"2345"
    assert client.get("/api/videos/v2").status_code == 404
    assert client.get("/api/search?kind=invalid").status_code == 422
    assert client.get("/api/search?limit=-1").status_code == 422
    assert client.get("/").status_code == 200


def test_http_rejects_files_outside_results(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps({"videos": [{"id": "v1", "media": "../outside.mp4"}]}), encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    assert client.get("/media/v1").status_code == 404


def test_source_failure_does_not_stop_batch(tmp_path, monkeypatch):
    from video_lab import pipeline, reporting
    good = {**video("ремонт"), "source": "good"}
    def fake_process(item, *args):
        if item["source"] == "bad":
            raise ValueError("broken media")
        return copy.deepcopy(good)
    monkeypatch.setattr(pipeline, "process_video", fake_process)
    monkeypatch.setattr(reporting, "export_results", lambda *args: None)
    result = pipeline.run([{"source": "bad"}, {"source": "good"}], tmp_path,
                          {"yolo": "yolov8n.pt", "whisper": "base", "device": "cpu"})
    assert len(result["videos"]) == 1
    assert result["failures"][0]["error"] == "ValueError: broken media"


def test_local_source_cache_stable_but_changed_bytes_invalidate(tmp_path):
    from video_lab.media import acquire
    source = tmp_path / "input.mp4"
    source.write_bytes(b"one")
    _, first = acquire(str(source), tmp_path / "download")
    _, second = acquire(str(source), tmp_path / "download")
    assert first == second
    source.write_bytes(b"two")
    _, third = acquire(str(source), tmp_path / "download")
    assert third["sha256"] != first["sha256"]
