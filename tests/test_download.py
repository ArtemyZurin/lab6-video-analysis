from pathlib import Path
from types import SimpleNamespace

import pytest
import yt_dlp

from video_lab.media import download_options, downloaded_file


def test_installed_node_enabled_without_deno(tmp_path, monkeypatch):
    monkeypatch.setattr("video_lab.media.shutil.which", lambda name: "/bin/node" if name == "node" else None)
    options = download_options(tmp_path)
    assert options["js_runtimes"] == {"node": {"path": "/bin/node"}}


@pytest.mark.parametrize("mode,expected", [("adaptive", "video+audio"), ("combined", "combined"), ("silent", "video")])
def test_format_selection_handles_separate_streams_and_fallbacks(tmp_path, mode, expected):
    video = {"format_id": "video", "url": "https://example.org/video.mp4", "ext": "mp4",
             "vcodec": "avc1", "acodec": "none", "height": 1080}
    audio = {"format_id": "audio", "url": "https://example.org/audio.m4a", "ext": "m4a",
             "vcodec": "none", "acodec": "mp4a", "abr": 128}
    combined = {"format_id": "combined", "url": "https://example.org/both.mp4", "ext": "mp4",
                "vcodec": "avc1", "acodec": "mp4a", "height": 360}
    formats = {"adaptive": [audio, video], "combined": [combined], "silent": [video]}[mode]
    with yt_dlp.YoutubeDL({**download_options(tmp_path), "check_formats": False}) as downloader:
        result = downloader.process_ie_result({"id": "fixture", "title": "Fixture", "formats": formats}, download=False)
    assert result["format_id"] == expected
    if mode == "adaptive":
        assert len(result["requested_formats"]) == 2
        assert result["ext"] == "mkv"


def test_final_merged_path_is_used_instead_of_predicted_extension(tmp_path):
    merged = tmp_path / "original.mkv"
    merged.write_bytes(b"merged fixture")
    downloader = SimpleNamespace(prepare_filename=lambda _: str(tmp_path / "original.mp4"))
    info = {"requested_downloads": [{"filepath": str(merged)}]}
    assert downloaded_file(info, downloader) == merged
    with pytest.raises(FileNotFoundError):
        downloaded_file({}, downloader)
