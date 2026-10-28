"""Оценить темы после анализа; эталонные группы не участвуют в обучении."""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from video_lab.common import ROOT, read_json, save_json, sha256
from video_lab.reporting import csv_write, report
from video_lab.semantics import group_videos, tokens


def agreement(videos, expected):
    predicted = [v["cluster"] for v in videos]
    if any(label is None for label in predicted):
        return {"adjusted_rand": None, "normalized_mutual_info": None}
    return {"adjusted_rand": float(adjusted_rand_score(expected, predicted)),
            "normalized_mutual_info": float(normalized_mutual_info_score(expected, predicted))}


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def evaluate(output, reference_path, baseline):
    index_path = output / "index.json"
    index = read_json(index_path)
    videos = index["videos"]
    reference = read_json(reference_path)
    expected = [reference["labels"][v["metadata"]["origin_url"]] for v in videos]
    if index["failures"] or len(videos) != len(reference["labels"]):
        raise ValueError("Для оценки нужен весь корпус без ошибок источников")
    if any(not v["segments"] for v in videos):
        raise ValueError("В каждом основном ролике ожидается распознанная речь")

    # Повторяем ТОТ ЖЕ алгоритм, удаляя только неречевые признаки.
    speech_videos = copy.deepcopy(videos)
    for video in speech_videos:
        video.update(title="", metadata={}, events=[])
    speech_topics = group_videos(speech_videos)
    full_metrics = agreement(videos, expected)
    speech_metrics = agreement(speech_videos, expected)
    rows = [{"video_id": v["id"], "title": v["title"],
             "origin_url": v["metadata"]["origin_url"], "reference_topic": label,
             "cluster": v["cluster"], "transcript_only_cluster": sv["cluster"],
             "speech_segments": len(v["segments"]),
             "speech_words": sum(len(tokens(s["text"])) for s in v["segments"])}
            for v, sv, label in zip(videos, speech_videos, expected)]
    result = {"index_sha256": sha256(index_path), "reference_sha256": sha256(reference_path),
              "selection": reference["selection"], "videos": rows,
              "full_features": {"topics": index["topics"], **full_metrics},
              "transcript_only": {"topics": speech_topics, **speech_metrics}}
    if baseline.is_file():
        old = read_json(baseline)
        result["baseline"] = {"index_sha256": sha256(baseline), "videos": len(old["videos"]),
                              "speech_segments": sum(len(v["segments"]) for v in old["videos"]),
                              "silhouette": old["topics"].get("silhouette")}
    save_json(output / "topic_evaluation.json", result)
    csv_write(output / "topic_evaluation.csv", rows, list(rows[0]))
    lines = ["# Проверка тематической группировки", "", reference["selection"], "",
             "Речь получена Whisper base; ручные тексты не подставлялись. Заголовки — названия исходных выпусков. "
             "В основной модели используются заголовок, распознанная речь и классы YOLO; описания и теги "
             "в локальном манифесте пусты. Полные метаданные загрузки сохранены отдельно в `../data/demo/*/source.json`.", "",
             "Контроль: повторно применён неизменённый TF-IDF + KMeans только к транскриптам, без названий, "
             "метаданных и объектов. k в обоих вариантах выбран по максимуму cosine silhouette. "
             "Экспертные метки прочитаны только для последующего сравнения; они не передаются в group_videos.", "",
             "## Автоматические метрики", "",
             "| Признаки | k | Silhouette | ARI | NMI |", "|---|---:|---:|---:|---:|"]
    for name, topics, metrics in [("Речь + заголовки + объекты", index["topics"], full_metrics),
                                  ("Только речь", speech_topics, speech_metrics)]:
        sil = topics.get("silhouette")
        lines.append(f"| {name} | {topics.get('selected_k')} | {sil:.5f} | "
                     f"{metrics['adjusted_rand']:.5f} | {metrics['normalized_mutual_info']:.5f} |")
    lines += ["", "ARI и NMI сравнивают разбиение с двумя заранее заданными широкими темами; "
              "значение 1 означает совпадение разбиений с точностью до номера кластера, а не точность ASR или детектора.", "",
              "| Видео | Эталонная широкая тема | Кластер | Только речь | Сегменты | Слова |",
              "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {md(row['title'])} | {row['reference_topic']} | {row['cluster']} | "
                     f"{row['transcript_only_cluster']} | {row['speech_segments']} | {row['speech_words']} |")
    for name, topics in [("Основная модель", index["topics"]), ("Только речь", speech_topics)]:
        lines += ["", f"## {name}", "", "| k | Cosine silhouette |", "|---:|---:|"]
        lines += [f"| {c['k']} | {c['silhouette']:.5f} |" for c in topics["candidates"]]
        for topic in topics["topics"]:
            titles = [v["title"] for v in videos if v["id"] in topic["video_ids"]]
            lines += ["", f"Кластер {topic['cluster']}: {', '.join(topic['keywords'])}. "
                      f"Ролики: {'; '.join(titles)}."]
    if "baseline" in result:
        old = result["baseline"]
        lines += ["", "## Сравнение с исходным набором", "",
                  f"Старый набор: {old['videos']} видео, {old['speech_segments']} сегментов речи, "
                  f"silhouette {old['silhouette']:.5f}. Новый: {len(videos)} видео, "
                  f"{sum(r['speech_segments'] for r in rows)} сегментов речи. "
                  "Алгоритм группировки и его параметры не менялись. Изменился сам корпус: "
                  "числа silhouette описывают разные выборки и не доказывают улучшение алгоритма. "
                  "Старые результаты и проверка сохранены в `../results_baseline/`."]
    lines += ["", "## Ограничения и ручной разбор", "",
              "Шесть роликов одного канала, две намеренно выбранные темы и не более первых 90 секунд каждого выпуска. "
              "Это проверка полезности на учебном примере, не независимый тест на произвольном архиве. "
              "Совпадение с широкими темами не означает, что внутри каждой группы все сюжеты одинаковы. "
              "Ручной разбор содержания и ошибок приведён в [VALIDATION.md](../VALIDATION.md). "
              "Отрицательный контроль без содержательной речи вынесен в `../results_control/` и не участвует в обучении.", "",
              "Машиночитаемые данные: [JSON](topic_evaluation.json), [CSV](topic_evaluation.csv). "
              "SHA-256 индекса и эталона записаны в JSON; после нового анализа повторите `python evaluate_topics.py`.", ""]
    (output / "TOPIC_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    report(index, output)
    print(f"Основная модель: {full_metrics}; только речь: {speech_metrics}")
    print(output / "TOPIC_VALIDATION.md")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--reference", type=Path, default=ROOT / "data" / "topic_reference.json")
    parser.add_argument("--baseline", type=Path, default=ROOT / "results_baseline" / "index.json")
    args = parser.parse_args()
    evaluate(args.results, args.reference, args.baseline)
