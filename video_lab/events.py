"""Объединение наблюдений в интервалы; частота детекций ≠ число разных людей."""
from collections import defaultdict


def object_events(frames, duration):
    events, active = [], {}
    for i, frame in enumerate(frames):
        time = frame["time"]
        end = frames[i + 1]["time"] if i + 1 < len(frames) else duration
        present = defaultdict(list)
        for box in frame["objects"]:
            present[box["label"]].append(box["confidence"])
        for label in list(active):
            if label not in present:
                events.append(active.pop(label))
        for label, confidences in present.items():
            if label not in active:
                active[label] = {"type": "object", "label": label, "start": time,
                                 "end": end, "confidence": max(confidences), "samples": 1,
                                 "frame": frame["image"]}
            else:
                event = active[label]
                n = event["samples"]
                event["confidence"] = (event["confidence"] * n + max(confidences)) / (n + 1)
                event["samples"] += 1
                event["end"] = end
    events.extend(active.values())
    return events


def build_events(frames, segments, audio, duration, scene_threshold):
    events = object_events(frames, duration)
    for frame in frames:
        if frame["scene_distance"] >= scene_threshold:
            events.append({"type": "scene", "label": "Смена сцены", "start": frame["time"],
                           "end": min(duration, frame["time"] + 0.1),
                           "value": frame["scene_distance"], "frame": frame["image"]})
    for seg in segments:
        events.append({"type": "speech", "label": seg["text"], "start": seg["start"],
                       "end": seg["end"], "avg_logprob": seg.get("avg_logprob")})
    current = None
    for row in audio:
        if row["peak"]:
            if current is None:
                current = {"type": "audio", "label": "Пик громкости", "start": row["start"],
                           "end": row["end"], "value": row["dbfs"]}
            else:
                current["end"] = row["end"]
                current["value"] = max(current["value"], row["dbfs"])
        elif current:
            events.append(current)
            current = None
    if current:
        events.append(current)
    events = [e for e in events if 0 <= e["start"] < e["end"] <= duration + 0.001]
    events.sort(key=lambda e: (e["start"], e["type"], e["label"]))
    for i, event in enumerate(events):
        event["id"] = f"e{i:05d}"
        event["start"], event["end"] = round(event["start"], 4), round(event["end"], 4)
    return events


def entity_statistics(frames, events, duration):
    stats = defaultdict(lambda: {"detections": 0, "frames": 0, "max_simultaneous": 0,
                                  "confidence_sum": 0.0, "intervals": 0, "seconds": 0.0})
    for frame in frames:
        counts = defaultdict(int)
        for box in frame["objects"]:
            label = box["label"]
            counts[label] += 1
            stats[label]["detections"] += 1
            stats[label]["confidence_sum"] += box["confidence"]
        for label, count in counts.items():
            stats[label]["frames"] += 1
            stats[label]["max_simultaneous"] = max(stats[label]["max_simultaneous"], count)
    for event in events:
        if event["type"] == "object":
            stats[event["label"]]["intervals"] += 1
            stats[event["label"]]["seconds"] += event["end"] - event["start"]
    result = []
    for label, row in sorted(stats.items()):
        row["mean_confidence"] = row.pop("confidence_sum") / row["detections"]
        row["frame_share"] = row["frames"] / len(frames)
        row["duration_share"] = row["seconds"] / duration
        result.append({"label": label, **row})
    return result
