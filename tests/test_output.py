from pathlib import Path

import pytest

from video_lab.common import ROOT
from video_lab.output import result_directory


@pytest.mark.parametrize("manifest", ["demo_local.json", "demo_sources.json"])
def test_demo_keeps_prepared_report(manifest):
    assert result_directory([{"source": "demo.mp4"}], ROOT / "data" / manifest) == ROOT / "results"


@pytest.mark.parametrize("source,folder", [
    ("my video.mp4", "results_my"),
    ("https://www.youtube.com/watch?v=example", "results_youtube"),
])
def test_default_folder_depends_on_source(source, folder):
    assert result_directory([{"source": source}]) == ROOT / folder


@pytest.mark.parametrize("source,wrong", [
    ("my.mp4", "results"), ("my.mp4", "results_youtube"),
    ("https://example.org/video", "results_my"), ("https://example.org/video", "results"),
])
def test_wrong_reserved_output_is_rejected_before_writing(source, wrong):
    with pytest.raises(ValueError, match="другого типа"):
        result_directory([{"source": source}], output=ROOT / wrong)


def test_mixed_sources_need_separate_folder(tmp_path):
    items = [{"source": "local.mp4"}, {"source": "https://example.org/video"}]
    with pytest.raises(ValueError, match="смешанного"):
        result_directory(items)
    with pytest.raises(ValueError, match="другого типа"):
        result_directory(items, output=ROOT / "results")
    assert result_directory(items, output=tmp_path / "experiment") == tmp_path / "experiment"


def test_explicit_custom_folder_and_correct_reserved_folder(tmp_path):
    items = [{"source": "local.mp4"}]
    assert result_directory(items, output=tmp_path) == tmp_path
    assert result_directory(items, output=ROOT / "results_my") == ROOT / "results_my"
