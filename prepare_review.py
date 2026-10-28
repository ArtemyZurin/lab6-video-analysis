"""Собрать проверяемые изображения и чувствительность к порогу, без автоматического вердикта."""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from video_lab.common import ROOT, read_json
from video_lab.reporting import csv_write


def main():
    directory = ROOT / "results"
    index = read_json(directory / "index.json")
    with (directory / "review_sample.csv").open(encoding="utf-8-sig", newline="") as file:
        sample = list(csv.DictReader(file))
    canvas = Image.new("RGB", (1200, 255 * len(sample)), "white")
    draw = ImageDraw.Draw(canvas)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 16) if font_path.exists() else ImageFont.load_default()
    for i, row in enumerate(sample):
        video = next(v for v in index["videos"] if v["id"] == row["video_id"])
        at = float(row["start"])
        frame_index = min(range(len(video["frames"])), key=lambda n: abs(video["frames"][n]["time"] - at))
        draw.text((10, i * 255 + 4), f"{i+1}. {video['title']} | {row['type']} {row['label']} | {row['start']}–{row['end']} s", fill="black", font=font)
        for j, n in enumerate([max(0, frame_index - 1), frame_index, min(len(video["frames"]) - 1, frame_index + 1)]):
            frame = video["frames"][n]
            image = Image.open(directory / frame["image"])
            image.thumbnail((390, 205))
            canvas.paste(image, (j * 400, i * 255 + 25))
            draw.text((j * 400 + 5, i * 255 + 231), f"t = {frame['time']:.3f} s", fill="black", font=font)
    canvas.save(directory / "review_contact_sheet.jpg", quality=90)
    rows = []
    for threshold in [0.4, 0.6, 0.8]:
        for video in index["videos"]:
            rows.append({"threshold": threshold, "video": video["title"], "frames": len(video["frames"]),
                         "boxes": sum(b["confidence"] >= threshold for f in video["frames"] for b in f["objects"]),
                         "person_frames": sum(any(b["label"] == "person" and b["confidence"] >= threshold for b in f["objects"]) for f in video["frames"])})
    csv_write(directory / "threshold_sensitivity.csv", rows, ["threshold", "video", "frames", "boxes", "person_frames"])
    print(directory / "review_contact_sheet.jpg")


if __name__ == "__main__":
    main()
