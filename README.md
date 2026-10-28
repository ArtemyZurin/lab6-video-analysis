# Лабораторная работа №6 (практика 6)

Система автоматического анализа видео 

Вход: локальные файлы или URL. Выход: детекции объектов, транскрипт, интервалы событий, статистика, тематическая группировка и поиск с переходом к нужной секунде.

## Версия на GitHub

В репозитории опубликованы код, манифесты источников, отчёты, индексы, таблицы, кадры с детекциями,
графики и результаты проверок. Видео, извлечённое аудио, веса моделей, окружение `.venv` и кэши
не включены. Сохранённые протоколы относятся к полному локальному запуску: после клонирования
для воспроизведения видео в плеере и проверки целостности нужно сначала загрузить и обработать набор.

```powershell
git clone https://github.com/ArtemyZurin/lab6-video-analysis.git
cd lab6-video-analysis
или скачать архив, распаковать, затем в папке с проектом:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
# Для загрузки YouTube нужен Node.js 22+ либо Deno в PATH
.\.venv\Scripts\python.exe prepare_demo.py --models
.\.venv\Scripts\python.exe lab6.py run --manifest data/demo_local.json
.\.venv\Scripts\python.exe evaluate_topics.py
.\.venv\Scripts\python.exe lab6.py verify
.\.venv\Scripts\python.exe lab6.py serve
Открыть интерфейс в браузере http://127.0.0.1:8006
```

После нового прогона идентификаторы видео могут измениться из-за другого пути к папке проекта.
Для обновления контактного листа выполните `python prepare_review.py`; ручные вердикты в
`VALIDATION.md` и `review_checked.csv` относятся к опубликованному запуску и требуют повторной проверки.
Файлы `results_my` и `results_youtube` содержат отчёты отдельных экспериментов; команды для их повторения
приведены ниже. Локальный пример требует своего файла, а исходный набор W3C/OpenCV описан в
`data/baseline_sources.json`.

## Результаты ##

**[Отчёт и результаты по 6 подготовленным видео](results/REPORT.md)**

**[Отчёт по своему локальному видео](results_my/REPORT.md)**

**[Отчёт по видео с YouTube](results_youtube/REPORT.md)**

**[Проверка качества](VALIDATION.md)** 

[Подробная проверка тематических групп](results/TOPIC_VALIDATION.md) ·
[Таймер — отдельный отрицательный контроль](results_control/REPORT.md) ·
[Исходный эксперимент на 5 образцах](results_baseline/REPORT.md)

Папка сохранения выбирается автоматически при `run`:

| Вход | Отчёт |
|---|---|
| Подготовленный набор: `--manifest data/demo_local.json` или `data/demo_sources.json` | `results/REPORT.md` |
| Свой локальный файл: `--input "путь к видео"` | `results_my/REPORT.md` |
| YouTube или другой URL: `--input "https://..."` | `results_youtube/REPORT.md` |

Эти папки находятся рядом с `lab6.py`. Их нельзя случайно использовать для другого типа входа: программа сообщит об ошибке до обработки. Для отдельного или смешанного эксперимента
можно указать свою папку через `--output`, например `results_mixed`.
`REPORT.md` обновляется после обработки соответствующего набора. `VALIDATION.md` —
отдельный разбор качества подготовленных видео; автоматически он не перезаписывается.


## Быстрый запуск готового результата

В PowerShell из папки лабораторной

Активация через `Activate.ps1` не требуется: запускайте Python окружения напрямую.
Окружение этой работы находится в подпапке `.venv` рядом с `lab6.py`.
Для уже установленной лабораторной повторять `python -m venv .venv` не нужно.

```powershell
.\.venv\Scripts\python.exe lab6.py serve
```

Открыть **http://127.0.0.1:8006**. Для просмотра готовых результатов интернет и загрузка моделей не требуются. Запрос `человек` находит класс `person`; английское слово из транскрипта находит реплику. Клик по результату или цветному интервалу перематывает плеер. Пустой запрос показывает все события. API: `/docs`, `/api/videos`, `/api/topics`, `/api/search?q=человек`.

## Установка на другом компьютере

Python 3.12, Windows/Linux. Окружение `.venv` не переносить между компьютерами.

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe lab6.py serve
```

Если после повторного создания окружения появляется `ModuleNotFoundError`, восстановите зависимости:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe lab6.py serve
```

`Permission denied` при создании `.venv` может означать, что его Python уже используется
работающим сервером. Завершите сервер через `Ctrl+C` в его терминале. Для обычного запуска
пересоздавать окружение не требуется. Блокировка `Activate.ps1` групповой политикой не
мешает приведённым командам прямого запуска; менять политику выполнения не нужно.

FFmpeg включён в `imageio-ffmpeg`, менять системный PATH не нужно. Технические метаданные извлекаются через PyAV/libavformat; при наличии `ffprobe` сохраняется также его полный JSON. FFmpeg, YOLO и Whisper работают локально. При первом анализе загружаются веса в `models/` (YOLOv8n и Whisper base). Системный Python не изменяется.

`requirements-lock.txt` фиксирует версии всех пакетов, необходимых проекту в проверенном окружении. Для точного повторения окружения вместо `requirements.txt` можно установить этот файл. `playwright` нужен только для необязательной браузерной проверки, обычному запуску он не требуется.

## Повторить эксперимент

```powershell
# Уже приложенные локальные видео; после первого запуска используются кэши
.\.venv\Scripts\python.exe lab6.py run --manifest data/demo_local.json
.\.venv\Scripts\python.exe evaluate_topics.py
.\.venv\Scripts\python.exe lab6.py verify
.\.venv\Scripts\python.exe lab6.py search "stars" --type speech
.\.venv\Scripts\python.exe -m pytest -q
```

Загрузка исходного набора с нуля (нужен интернет):

```powershell
.\.venv\Scripts\python.exe prepare_demo.py --models
.\.venv\Scripts\python.exe lab6.py run --manifest data/demo_local.json
.\.venv\Scripts\python.exe evaluate_topics.py
```

Сбор использует yt-dlp. Основной набор — шесть разных выпусков National Geographic 101 с английской речью:
Solar System, Black Holes, Stars (астрономия), Volcanoes, Earthquakes, Continental Drift
(геологические процессы). Берутся первые 90 секунд, а у Continental Drift — 72 секунды:
исключён встроенный анонс Volcanoes, начинающийся на 73.38 с и повторяющий речь другого видео набора.
Это три примера на каждую широкую тему; требование «не менее пяти видео» соблюдено.
Ссылки, SHA-256 и время получения находятся в `data/demo/*/source.json`; список — `data/demo_sources.json`.
Полные описания загрузки сохранены в квитанциях; в анализ подготовленных фрагментов передаются оригинальные
заголовки, распознанная речь и классы объектов. Ожидаемые широкие темы в `data/topic_reference.json`
читает только оценочный скрипт. В контрольном варианте он исключает заголовки и объекты и повторяет
группировку только по речи. `evaluate_topics.py` обновляет `TOPIC_VALIDATION.md` и JSON/CSV оценки;
ручной разбор в `VALIDATION.md` обновляется отдельно.

Для повторения именно этого эксперимента используйте `prepare_demo.py` и затем `data/demo_local.json`:
ограничение длительности применяет подготовительный скрипт. Прямой `run --manifest data/demo_sources.json`
обрабатывает полные исходные видео и даст другой эксперимент.

Старые пять образцов W3C/OpenCV сохранены в `results_baseline/`, их манифест — `data/baseline_local.json`.
Таймер W3C не участвует в основных темах. Его можно проверить отдельно:

```powershell
.\.venv\Scripts\python.exe lab6.py run --manifest data/control_local.json --output results_control
.\.venv\Scripts\python.exe lab6.py verify --results results_control --minimum-videos 1
```

Видео скачиваются для локального учебного анализа; приложение ничего не публикует.

## Свои файлы и URL

```powershell
.\.venv\Scripts\python.exe lab6.py run --input "D:\Видео\лекция.mp4" --language ru --output results_my
.\.venv\Scripts\python.exe lab6.py run --input "https://www.youtube.com/watch?v=ID" --output results_youtube
.\.venv\Scripts\python.exe lab6.py serve --results results_my
.\.venv\Scripts\python.exe lab6.py search "завод" --results results_my --type speech
```

Вместо `ID` нужна действующая ссылка. Поддержка конкретного хостинга зависит от yt-dlp и доступности ролика; защищённые или недоступные файлы попадут в журнал ошибок.

## Проверка своего локального видео (пример):

```powershell
.\.venv\Scripts\python.exe lab6.py run --input "E:\downloads1\WDSU Best Newscast LAB  _30 second clip.mp4" --language en --output results_my
.\.venv\Scripts\python.exe lab6.py verify --results results_my --minimum-videos 1
.\.venv\Scripts\python.exe lab6.py serve --results results_my
```

Открыт интерфейс http://127.0.0.1:8006. Введено слово из речи или название объекта и выполнено сравнение найденного момента с видео.


**[Отчёт сохранился в](results_my/REPORT.md)**

Каждый запуск run формирует индекс только для переданных ему видео; чтобы обработать несколько вместе, перечислите их пути или ссылки после --input через пробел.

## Загрузка с YouTube (пример):

Прямая загрузка ссылки `https://www.youtube.com/watch?v=9iDXWx7GtZQ` проверена
Видео и звук скачаны, объединены, затем обработаны YOLO и Whisper.

```powershell
.\.venv\Scripts\python.exe lab6.py run --input "https://www.youtube.com/watch?v=9iDXWx7GtZQ" --language en --output results_youtube
.\.venv\Scripts\python.exe lab6.py serve --results results_youtube
```
**[Отчёт сохранился в](results_youtube/REPORT.md)**

Для YouTube необходим установленный **Node.js 22+ либо Deno** в PATH: программа автоматически
подключает найденный runtime. Компонент `yt-dlp-ejs` устанавливается вместе с зависимостями
из `requirements.txt`. Версии `yt-dlp` и `yt-dlp-ejs` закреплены совместимой парой.
Настройка соответствует [инструкции yt-dlp по EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

Загрузчик поддерживает отдельные дорожки видео и аудио: скачивает их и объединяет FFmpeg
в MKV, затем готовит MP4 для плеера. Если доступны только единый файл или видео без звука,
используется соответствующий вариант. Это устраняет ограничение прежнего выбора `best[ext=mp4]/best`.

При ошибке `Requested format is not available` сначала проверьте зависимости и список форматов:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
node --version
.\.venv\Scripts\python.exe -m yt_dlp --js-runtimes node --list-formats "https://www.youtube.com/watch?v=ID"
```

Если используется Deno, замените `--js-runtimes node` на `--js-runtimes deno`.
При смене окружения Node.js/Deno устанавливается отдельно от Python-зависимостей.

Для набора создайте JSON:

```json
[
  {"source": "video1.mp4", "title": "Ремонт завода", "language": "ru", "interval": 0.5},
  {"source": "https://example.org/video2.mp4", "language": "en", "interval": 1.0}
]
```

Относительные пути внутри манифеста отсчитываются **от JSON-файла**, в `--input` — от текущей папки. Без `--output` папка результатов выбирается по таблице в разделе «Результаты». Явный относительный `--output` отсчитывается от текущей папки. Для разных экспериментов используйте разные папки: индекс содержит только источники текущего запуска. Исходные пользовательские файлы не меняются.

| Параметр | Значение и смысл |
|---|---|
| `--interval 0.5` | Один кадр примерно каждые 0.5 с; без параметра — адаптивный выбор по первым 8 с |
| `--confidence 0.4` | Порог YOLO; увеличение уменьшает ложные детекции и полноту |
| `--scene-threshold 0.45` | Порог изменения HSV-гистограммы |
| `--language ru` | Язык ASR; без параметра авто, значение в манифесте имеет приоритет |
| `--whisper base` | Модель ASR; доступны tiny/base/small/medium/large/turbo |
| `--device cpu` | Устройство для моделей; для CUDA можно указать `cuda:0` |
| `--force` | Пересчитать анализ, игнорируя кэш |
| `verify --minimum-videos 1` | Проверка отдельного эксперимента на одном ролике |

## Соответствие заданию

| Требование | Реализация и артефакт |
|---|---|
| Сбор и метаданные | `media.py`: yt-dlp, копирование локального файла, SHA-256; `source.json`, `metadata.json` |
| Декомпозиция | Потоковое декодирование с PTS, кадры JPEG, mono PCM 16 kHz `audio.wav` |
| Визуальные признаки и объекты | YOLOv8n; рамки, confidence, яркость, резкость; `frames.jsonl`, `visual_features.csv` |
| Речь и громкость | Whisper base с временными метками слов/сегментов, RMS/dBFS; `whisper_raw.json`, `transcript.json`, `audio_features.json` |
| Значимые события | Интервалы присутствия класса, смены сцен, речь, пики; `events.csv` |
| Статистика сущностей | Детекции, доли кадров, максимум объектов одновременно, длительности; `entities.csv`, `summary.png` |
| Тематическая группировка | Русская лемматизация, TF-IDF, KMeans, выбор k по cosine silhouette; `topics.json`, `topic_assignments.csv` |
| Интерфейс | FastAPI + HTML/JS: плеер, темы, поиск, цветные интервалы, переход по клику |
| Проверка результата | `verification.json`, тесты, `review_sample.csv`, `review_contact_sheet.jpg`, `VALIDATION.md` |

Рамки на кадрах — **наблюдения**, а не уникальные люди/предметы. Сцены выделяются по изменению изображения; распознавание конкретного места и нейросетевой классификатор сцен не заявляются. Поиск лемматизирует русский текст и понимает основные русские названия классов, но перевод всех английских реплик и произвольный поиск по смыслу не выполняет.

## Структура

```text
lab6.py                команды run / serve / search / verify
prepare_demo.py        загрузка и подготовка корпуса
prepare_review.py      изображения для проверки и сравнение порогов
evaluate_topics.py     проверка групп по эталону и вариант только по речи
browser_check.py       необязательная проверка интерфейса в Edge
video_lab/             сбор, модели, события, темы, сервер, отчёт
data/                  манифесты и исходные образцы
models/                локальный кэш весов
results/               готовый индекс, таблицы, графики, отчёт
tests/                 проверки интервалов, аудио, поиска, кэша, HTTP
```

Ошибка одного ролика не прекращает обработку остальных, причина записывается в `failures.json` и `pipeline.log`; итоговый код возврата — 1. Отсутствие аудио/речи явно отмечается. Подозрительные ASR-сегменты сохраняются в `rejected_segments.json`, но исключаются из поиска: фильтры эвристические и могут отклонить настоящую тихую или повторяющуюся речь. Длительные ролики требуют диска для промежуточных кадров и памяти для аудио Whisper; кадры целиком в RAM не накапливаются.

Документация используемых API: [Ultralytics](https://docs.ultralytics.com/modes/predict/), [Whisper](https://github.com/openai/whisper), [yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp), [PyAV](https://pyav.org/docs/stable/).
