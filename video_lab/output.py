"""Папки результатов для подготовленного набора, локальных файлов и URL."""
from pathlib import Path

from .common import ROOT


def result_directory(items, manifest=None, output=None):
    demo_manifests = {ROOT / "data" / "demo_local.json", ROOT / "data" / "demo_sources.json"}
    if manifest is not None and Path(manifest).resolve() in demo_manifests:
        expected = "results"
    else:
        remote = [item["source"].startswith(("http://", "https://")) for item in items]
        expected = "results_youtube" if all(remote) else "results_my" if not any(remote) else None
    if output is None:
        if expected is None:
            raise ValueError("Для смешанного набора файлов и URL задайте отдельную папку: --output results_mixed")
        return ROOT / expected
    destination = Path(output).resolve()
    reserved = {ROOT / name for name in ("results", "results_my", "results_youtube")}
    if destination in reserved and destination != (ROOT / expected if expected else None):
        suggestion = f"--output {expected}" if expected else "--output results_mixed"
        raise ValueError(f"Папка {destination.name} предназначена для другого типа входа. "
                         f"Для этого запуска используйте {suggestion} или отдельную папку эксперимента.")
    return destination
