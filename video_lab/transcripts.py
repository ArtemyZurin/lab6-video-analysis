"""Прозрачные эвристики качества ASR; исходный вывод Whisper всегда сохраняется."""
import re


def clean_segments(raw, duration):
    accepted, rejected = [], []
    last_text = None
    for original in raw:
        seg = {"start": max(0.0, float(original["start"])), "end": min(duration, float(original["end"])),
               "text": original["text"].strip(), "avg_logprob": float(original.get("avg_logprob", 0)),
               "no_speech_prob": float(original.get("no_speech_prob", 0)),
               "compression_ratio": float(original.get("compression_ratio", 0))}
        text = seg["text"]
        reason = None
        if not re.search(r"\w", text) or seg["end"] <= seg["start"]:
            reason = "empty_or_invalid_segment"
        elif seg["no_speech_prob"] > 0.6:
            reason = "high_no_speech_probability"
        elif seg["avg_logprob"] < -1.0:
            reason = "low_log_probability"
        elif seg["compression_ratio"] > 2.4 or re.search(r"(.)\1{9,}", text):
            reason = "repetitive_output"
        elif text.casefold() == last_text:
            reason = "consecutive_duplicate"
        last_text = text.casefold()
        if reason:
            rejected.append({**seg, "reason": reason})
        else:
            accepted.append(seg)
    return accepted, rejected
