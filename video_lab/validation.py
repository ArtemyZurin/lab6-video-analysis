from pathlib import Path

from .common import read_json, save_json


def verify(directory: Path, minimum=5):
    index = read_json(directory / "index.json")
    errors, count = [], 0
    if len(index["videos"]) < minimum:
        errors.append(f"Нужно минимум {minimum} роликов; найдено {len(index['videos'])}")
    if index["failures"]:
        errors.append(f"Не обработаны источники: {len(index['failures'])}")
    for video in index["videos"]:
        if not (directory / video["media"]).is_file():
            errors.append(f"Нет видео {video['id']}")
        times = [f["time"] for f in video["frames"]]
        if not times or any(a >= b for a, b in zip(times, times[1:])):
            errors.append(f"Неправильная шкала кадров {video['id']}")
        for frame in video["frames"]:
            if not (directory / frame["image"]).is_file():
                errors.append(f"Нет кадра {frame['image']}")
        for event in video["events"]:
            count += 1
            if not 0 <= event["start"] < event["end"] <= video["duration"] + 0.001:
                errors.append(f"Событие вне длительности: {video['id']} {event['id']}")
        if not video["segments"] and not video["warnings"]:
            errors.append(f"Пустой транскрипт без предупреждения: {video['id']}")
        for stat in video["entities"]:
            if not 0 < stat["frame_share"] <= 1 or not 0 <= stat["duration_share"] <= 1.001:
                errors.append(f"Неверная статистика: {video['id']} {stat['label']}")
    for artifact in ("visual_features.csv", "events.csv", "entities.csv", "topics.json", "topic_assignments.csv", "summary.png", "timeline.png", "REPORT.md"):
        if not (directory / artifact).is_file():
            errors.append(f"Нет артефакта {artifact}")
    save_json(directory / "verification.json", {"passed": not errors, "videos": len(index["videos"]), "events": count, "errors": errors})
    if errors:
        raise ValueError("\n".join(errors))
    return [f"OK: {len(index['videos'])} роликов, {count} событий; метки времени, файлы и статистика согласованы.",
            "OK: пять выходных артефактов сформированы."]
