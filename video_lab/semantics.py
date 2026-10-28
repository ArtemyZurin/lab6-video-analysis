"""Лемматизация русского текста, поиск и воспроизводимая группировка."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics import silhouette_score

RU_STOP = set("и в во на с со а но или из за под для по к у от до это этот тот как что чтобы который быть был есть мы вы они он она оно я ты не да нет о об при же уже ещё все весь свой наш ваш там тут так также только очень мочь стать когда где чем кто его её их бы то ли ну вот через после перед между один два раз самый мой твой себя каждый такой потому поэтому".split())
ALIASES = {
    "person": "человек люди мужчина женщина", "car": "автомобиль машина авто",
    "bus": "автобус", "truck": "грузовик", "bicycle": "велосипед",
    "motorcycle": "мотоцикл", "train": "поезд", "boat": "лодка корабль",
    "dog": "собака", "cat": "кот кошка", "bird": "птица", "horse": "лошадь",
    "tv": "телевизор экран", "laptop": "ноутбук", "cell phone": "телефон",
    "chair": "стул", "couch": "диван", "bottle": "бутылка", "cup": "чашка",
    "book": "книга", "sports ball": "мяч", "airplane": "самолёт",
}


@lru_cache(maxsize=1)
def morphology():
    import pymorphy3
    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=50000)
def lemma(word):
    return morphology().parse(word)[0].normal_form if re.search("[а-яё]", word) else word


def tokens(text, remove_stop=False):
    words = [lemma(w) for w in re.findall(r"[a-zа-яё0-9]+", text.lower().replace("ё", "е"))]
    if remove_stop:
        words = [w for w in words if w not in RU_STOP and w not in ENGLISH_STOP_WORDS and len(w) > 1]
    return words


def searchable_text(event):
    label = event["label"]
    return label + " " + ALIASES.get(label, "")


def search(index, query, kind="all", limit=100):
    wanted = set(tokens(query.strip()))
    hits = []
    for video in index["videos"]:
        for event in video["events"]:
            if kind != "all" and event["type"] != kind:
                continue
            if wanted and not wanted.issubset(set(tokens(searchable_text(event)))):
                continue
            hits.append({**event, "video_id": video["id"], "title": video["title"],
                         "cluster": video.get("cluster"),
                         "url": f"/media/{video['id']}#t={event['start']:.3f}"})
    return hits[:limit]


def group_videos(videos):
    """KMeans: подбор k по cosine silhouette; пустые документы не получают тему."""
    docs = []
    for video in videos:
        metadata = video["metadata"]
        docs.append(" ".join(tokens(" ".join([
            video["title"], metadata.get("description") or "",
            " ".join(metadata.get("tags") or []), " ".join(metadata.get("categories") or []),
            " ".join(s["text"] for s in video["segments"]),
            " ".join(sorted({e["label"] for e in video["events"] if e["type"] == "object"})),
        ]), remove_stop=True)))
    valid = [i for i, doc in enumerate(docs) if doc.strip()]
    for video in videos:
        video["cluster"] = None
        video["topic_words"] = []
    if not valid:
        return {"method": "TF-IDF + KMeans", "topics": [], "candidates": [], "reason": "empty vocabulary"}
    vectorizer = TfidfVectorizer(max_features=5000, token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform([docs[i] for i in valid])
    distinct = len({tuple(row) for row in matrix.toarray()})
    candidates, best, best_score = [], None, -2.0
    for k in range(2, min(6, len(valid) - 1, distinct) + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=10).fit(matrix)
        count = len(set(model.labels_))
        if 1 < count < len(valid):
            score = float(silhouette_score(matrix, model.labels_, metric="cosine"))
            candidates.append({"k": k, "silhouette": score})
            if score > best_score:
                best, best_score = model, score
    if best is None:
        best = KMeans(n_clusters=1, random_state=42, n_init=10).fit(matrix)
    words = vectorizer.get_feature_names_out()
    topics = []
    for cluster, center in enumerate(best.cluster_centers_):
        top = [str(words[i]) for i in np.argsort(center)[::-1][:10] if center[i] > 0]
        ids = [videos[valid[i]]["id"] for i, lab in enumerate(best.labels_) if lab == cluster]
        topics.append({"cluster": cluster, "keywords": top, "video_ids": ids,
                       "count": len(ids), "share": len(ids) / len(videos)})
    for i, label in zip(valid, best.labels_):
        videos[i]["cluster"] = int(label)
        videos[i]["topic_words"] = topics[int(label)]["keywords"]
    return {"method": "TF-IDF + KMeans", "selected_k": len(topics), "seed": 42,
            "silhouette": best_score if candidates else None, "candidates": candidates,
            "topics": topics, "unassigned": len(videos) - len(valid),
            "note": "Доли роликов в кластерах, не вероятности тем. Малый корпус даёт неустойчивую оценку."}
