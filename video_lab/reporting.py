from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path

from .common import clock, read_json, save_json, sha256


def csv_write(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_results(index, output):
    videos = index["videos"]
    entities = [{"video_id": v["id"], "title": v["title"], **row} for v in videos for row in v["entities"]]
    events = [{"video_id": v["id"], "title": v["title"], **row} for v in videos for row in v["events"]]
    features = [{"video_id": v["id"], **row, "objects": ", ".join(b["label"] for b in row["objects"])}
                for v in videos for row in v["frames"]]
    csv_write(output / "visual_features.csv", features,
              ["video_id", "time", "brightness", "sharpness", "scene_distance", "objects", "image"])
    csv_write(output / "events.csv", events,
              ["video_id", "title", "id", "type", "start", "end", "label", "confidence", "value", "frame"])
    csv_write(output / "entities.csv", entities,
              ["video_id", "title", "label", "detections", "frames", "frame_share", "max_simultaneous",
               "mean_confidence", "intervals", "seconds", "duration_share"])
    save_json(output / "topics.json", index["topics"])
    csv_write(output / "topic_assignments.csv", [{"video_id": v["id"], "title": v["title"],
               "cluster": v["cluster"], "keywords": ", ".join(v["topic_words"])} for v in videos],
              ["video_id", "title", "cluster", "keywords"])
    # Проверочная выборка сохраняется отдельно: повторный запуск не затирает ручную оценку.
    rng = random.Random(42)
    sample = []
    for video in videos[:5]:
        visual = [e for e in events if e["video_id"] == video["id"] and e["type"] in {"object", "scene"}]
        if visual:
            sample.append(rng.choice(visual))
    csv_write(output / "review_sample.csv", [{**e, "verdict": "", "comment": ""} for e in sample],
              ["video_id", "title", "id", "type", "start", "end", "label", "frame", "verdict", "comment"])
    plot_results(index, output)
    report(index, output)


def plot_results(index, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    videos = index["videos"]
    counts = Counter()
    for v in videos:
        for e in v["entities"]:
            counts[e["label"]] += e["detections"]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    labels, values = zip(*counts.most_common(12)) if counts else ([], [])
    axes[0].barh(list(labels)[::-1], list(values)[::-1], color="#258b91")
    axes[0].set(title="Детекции на выбранных кадрах", xlabel="Число рамок (не уникальных объектов)")
    topics = index["topics"]["topics"]
    axes[1].bar([str(t["cluster"]) for t in topics], [t["count"] for t in topics], color="#5871ca")
    axes[1].set(title="Тематическое распределение", xlabel="Кластер", ylabel="Число роликов")
    figure.savefig(output / "summary.png", dpi=160)
    plt.close(figure)
    colors = {"object": "#258b91", "speech": "#5871ca", "scene": "#d38e21", "audio": "#d15974"}
    figure, axes = plt.subplots(max(1, len(videos)), 1, figsize=(12, max(3, len(videos) * 2.1)), squeeze=False, layout="constrained")
    for axis, v in zip(axes.flat, videos):
        for row, kind in enumerate(colors):
            intervals = [(e["start"], max(0.1, e["end"] - e["start"])) for e in v["events"] if e["type"] == kind]
            axis.broken_barh(intervals, (row - 0.3, 0.6), facecolors=colors[kind], alpha=0.7)
        axis.set(yticks=range(4), yticklabels=["Объекты", "Речь", "Сцены", "Громкость"],
                 xlim=(0, v["duration"]), title=v["title"], xlabel="Время, с")
    figure.savefig(output / "timeline.png", dpi=160)
    plt.close(figure)


def report(index, output):
    videos, config = index["videos"], index["config"]
    total_frames = sum(len(v["frames"]) for v in videos)
    total_events = sum(len(v["events"]) for v in videos)
    lines = ["# Лабораторная работа №6 (практика 6)", "", "## Автоматический анализ и семантическая обработка видео", "",
        "Основание: lecture7_video_analysis.pptx, слайды 11, 17–21 и заметки докладчика. "
        "Цель — собрать видео, выделить визуальные и звуковые события, сгруппировать ролики и найти нужный момент.", "",
        "## Полученные результаты", "",
        f"Успешно обработано **{len(videos)}** роликов, **{total_frames}** кадров, **{total_events}** событий. "
        f"Ошибок источников: **{len(index['failures'])}**. Результаты получены запуском моделей, без подстановки разметки.", "",
        "| Видео | Длительность | Шаг кадров | Кадры | Сегменты речи | События | Кластер |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for v in videos:
        title = v['title'].replace('|', '\\|')
        lines.append(f"| {title} | {clock(v['duration'])} | {v['interval']} с | {len(v['frames'])} | "
                     f"{len(v['segments'])} | {len(v['events'])} | {v['cluster']} |")
    lines += ["", "## Пять артефактов из задания", "",
        "1. `visual_features.csv`, `videos/*/frames.jsonl`, `videos/*/frames/*.jpg`: рамки YOLO, классы, уверенность, яркость, резкость, изменение гистограммы.",
        "2. `events.csv`: интервалы присутствия объектов, речь, смены сцен и пики громкости.",
        "3. `entities.csv`, `summary.png`: частоты детекций, доля кадров, интервалы и приблизительная длительность присутствия.",
        "4. `python lab6.py serve`: поиск, плеер, кликабельная временная шкала; `timeline.png` — её статическое представление.",
        "5. `topics.json`, `topic_assignments.csv`: темы с ключевыми словами, доли роликов, перебор k и silhouette.", "",
        "![Статистика](summary.png)", "", "![Временная шкала](timeline.png)", "",
        "## Методика и параметры", "",
        f"Детектор **{config['yolo']}**, порог **{config['confidence']}**; ASR **Whisper {config['whisper']}**, устройство **{config['device']}**. "
        "Nano уменьшает затраты на CPU; base поддерживает русский и английский и подходит для коротких роликов. "
        "Порог 0.4 — исходная рабочая гипотеза из лекции, а не результат оптимизации на размеченном корпусе.", "",
        "Кадры читаются потоком по PTS. Автовыбор шага: разница уменьшенных кадров в первых 8 с > 0.07 → 0.5 с; "
        "иначе 1 с, для статичных роликов длиннее 10 минут — 2 с. Интервал можно задать для каждого файла. "
        "Пилот не гарантирует обнаружение динамики в конце ролика; краткие события между отсчётами могут быть пропущены.", "",
        f"Граница сцены — расстояние Бхаттачарьи между HSV-гистограммами ≥ {config['scene_threshold']}. "
        "Это эвристика монтажа, а не классификация места. Яркость — средняя интенсивность, резкость — дисперсия Лапласиана.", "",
        "Звук преобразуется в PCM mono 16 kHz; громкость — RMS в окнах по 1 с, в dBFS. "
        "Пик: значение не ниже max(-35 dBFS, 90-й процентиль данного файла). Соседние окна объединяются.", "",
        "Объекты одного класса объединяются только на последовательных выбранных кадрах. Граница справа — следующий отсчёт; "
        "погрешность порядка шага выборки. Детекции не являются числом уникальных людей или машин: трекинга идентичностей нет.", "",
        "Текст: транскрипт, метаданные и классы объектов → русская лемматизация, русские/английские стоп-слова, TF-IDF (до 5000 признаков), "
        "KMeans (seed=42, n_init=10). k выбирается по максимуму cosine silhouette среди 2…min(6, n−1, число различных документов). "
        "Если выбор невозможен, используется один кластер. Пустые документы остаются без темы.", "",
        "## Тематические группы", ""]
    for topic in index["topics"]["topics"]:
        titles = [v["title"] for v in videos if v["id"] in topic["video_ids"]]
        lines.append(f"- Кластер {topic['cluster']} ({topic['share']:.0%}): {', '.join(topic['keywords'])}. Ролики: {'; '.join(titles)}.")
    lines += ["", f"Silhouette: {index['topics'].get('silhouette')}. На малом корпусе эта оценка не доказывает тематическую устойчивость.", "",
        "## Проверка и ограничения", "",
        "Стратифицированная случайная выборка визуальных событий (seed=42, по одному из первых пяти роликов) записана в `review_sample.csv`. "
        "Результат визуальной проверки и разбор тематических групп приведены в `../VALIDATION.md`, если этот файл подготовлен. "
        "Автоматические проверки целостности не подменяют просмотр кадров и прослушивание речи.", "",
        "Состав данного запуска перечислен в таблице выше; источники и параметры сохранены в индексе и метаданных. "
        "Небольшой учебный набор не представляет весь видеоархив и не даёт общей оценки качества ASR. "
        "Для русских файлов поддержан параметр `--language ru`; оценки WER/mAP не заявляются без эталонной разметки.", "",
        "Whisper может ошибаться на музыке, именах и коротких репликах. YOLO распознаёт только свои классы. "
        "Поиск использует леммы и словарь русских названий объектов, но не является нейросетевым поиском синонимов. "
        "Эмоции, биометрия и внимание людей не оцениваются.", "",
        "## Источники и воспроизводимость", "",
        "Ссылки и SHA-256 файлов сохранены в `videos/*/source.json`; исходные URL демонстрационного корпуса — в `../data/demo_sources.json`. "
        "При локальном запуске происхождение корпуса дополнительно сохранено в `../data/demo/*/source.json`. "
        "Полные промежуточные файлы включают аудио, транскрипт, метаданные и детекции. "
        "Кэш результата привязан к содержимому источника, параметрам и версии пайплайна.", "",
        "Документация: [Ultralytics](https://docs.ultralytics.com/modes/predict/), "
        "[Whisper](https://github.com/openai/whisper), [yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp).", ""]
    for v in videos:
        for warning in v["warnings"]:
            lines.append(f"- Предупреждение {v['title']}: {warning}")
    for failure in index["failures"]:
        lines.append(f"- Ошибка {failure['source']}: {failure['error']}")
    evaluation = output / "topic_evaluation.json"
    if evaluation.is_file() and read_json(evaluation).get("index_sha256") == sha256(output / "index.json"):
        lines += ["", "## Дополнительный эксперимент с темами", "",
                  "[Сравнение с эталонными темами и группировка только по речи](TOPIC_VALIDATION.md). "
                  "Оценка относится к текущему индексу; его SHA-256 записан в `topic_evaluation.json`.", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
