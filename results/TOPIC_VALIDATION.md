# Проверка тематической группировки

Выбраны шесть разных выпусков одного канала: три об астрономии, три о геологических процессах. Анализируются первые 90 секунд. Исключение: Continental Drift ограничен 72 секундами, поскольку на 73.38 с начинается встроенный анонс Volcanoes, дублирующий другой ролик корпуса. Анонс исключён после просмотра первичного транскрипта, до расчёта оценок соответствия темам. Метки не используются для выбора k или параметров TF-IDF/KMeans.

Речь получена Whisper base; ручные тексты не подставлялись. Заголовки — названия исходных выпусков. В основной модели используются заголовок, распознанная речь и классы YOLO; описания и теги в локальном манифесте пусты. Полные метаданные загрузки сохранены отдельно в `../data/demo/*/source.json`.

Контроль: повторно применён неизменённый TF-IDF + KMeans только к транскриптам, без названий, метаданных и объектов. k в обоих вариантах выбран по максимуму cosine silhouette. Экспертные метки прочитаны только для последующего сравнения; они не передаются в group_videos.

## Автоматические метрики

| Признаки | k | Silhouette | ARI | NMI |
|---|---:|---:|---:|---:|
| Речь + заголовки + объекты | 2 | 0.05339 | 1.00000 | 1.00000 |
| Только речь | 2 | 0.05682 | 1.00000 | 1.00000 |

ARI и NMI сравнивают разбиение с двумя заранее заданными широкими темами; значение 1 означает совпадение разбиений с точностью до номера кластера, а не точность ASR или детектора.

| Видео | Эталонная широкая тема | Кластер | Только речь | Сегменты | Слова |
|---|---|---:|---:|---:|---:|
| Solar System 101 \| National Geographic | Астрономия | 0 | 0 | 17 | 210 |
| Black Holes 101 \| National Geographic | Астрономия | 0 | 0 | 10 | 156 |
| Stars 101 \| National Geographic | Астрономия | 0 | 0 | 24 | 185 |
| Volcanoes 101 \| National Geographic | Геологические процессы | 1 | 1 | 21 | 225 |
| Earthquakes 101 \| National Geographic | Геологические процессы | 1 | 1 | 15 | 233 |
| Continental Drift 101 \| National Geographic | Геологические процессы | 1 | 1 | 17 | 210 |

## Основная модель

| k | Cosine silhouette |
|---:|---:|
| 2 | 0.05339 |
| 3 | 0.04770 |
| 4 | 0.03686 |
| 5 | 0.02505 |

Кластер 0: stars, black, solar, holes, systems, stellar, luminosity, sun, planets, hole. Ролики: Solar System 101 | National Geographic; Black Holes 101 | National Geographic; Stars 101 | National Geographic.

Кластер 1: volcanoes, continents, plates, tectonic, earth, magma, violent, planet, ground, crust. Ролики: Volcanoes 101 | National Geographic; Earthquakes 101 | National Geographic; Continental Drift 101 | National Geographic.

## Только речь

| k | Cosine silhouette |
|---:|---:|
| 2 | 0.05682 |
| 3 | 0.04930 |
| 4 | 0.03770 |
| 5 | 0.02633 |

Кластер 0: stars, black, solar, holes, systems, stellar, luminosity, sun, hole, universe. Ролики: Solar System 101 | National Geographic; Black Holes 101 | National Geographic; Stars 101 | National Geographic.

Кластер 1: continents, volcanoes, plates, tectonic, earth, magma, violent, planet, ground, crust. Ролики: Volcanoes 101 | National Geographic; Earthquakes 101 | National Geographic; Continental Drift 101 | National Geographic.

## Сравнение с исходным набором

Старый набор: 5 видео, 7 сегментов речи, silhouette 0.06876. Новый: 6 видео, 104 сегментов речи. Алгоритм группировки и его параметры не менялись. Изменился сам корпус: числа silhouette описывают разные выборки и не доказывают улучшение алгоритма. Старые результаты и проверка сохранены в `../results_baseline/`.

## Ограничения и ручной разбор

Шесть роликов одного канала, две намеренно выбранные темы и не более первых 90 секунд каждого выпуска. Это проверка полезности на учебном примере, не независимый тест на произвольном архиве. Совпадение с широкими темами не означает, что внутри каждой группы все сюжеты одинаковы. Ручной разбор содержания и ошибок приведён в [VALIDATION.md](../VALIDATION.md). Отрицательный контроль без содержательной речи вынесен в `../results_control/` и не участвует в обучении.

Машиночитаемые данные: [JSON](topic_evaluation.json), [CSV](topic_evaluation.csv). SHA-256 индекса и эталона записаны в JSON; после нового анализа повторите `python evaluate_topics.py`.
