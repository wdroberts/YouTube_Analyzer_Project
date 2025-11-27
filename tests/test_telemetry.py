import os
from pathlib import Path
import tempfile

from telemetry import evaluate_health_alerts, get_directory_size_mb


def test_get_directory_size_mb_empty(tmp_path):
    trash = tmp_path / "trash"
    trash.mkdir()
    assert get_directory_size_mb(trash) == 0.0


def test_get_directory_size_mb_counts_files(tmp_path):
    trash = tmp_path / "trash"
    trash.mkdir()
    file_path = trash / "file.txt"
    file_path.write_bytes(b"x" * 1024)
    assert get_directory_size_mb(trash) >= 0.0009


def test_evaluate_health_alerts_trash_limit(tmp_path):
    trash = tmp_path / "trash"
    trash.mkdir()
    large_file = trash / "log.bin"
    large_file.write_bytes(b"x" * 1024 * 1024)  # 1 MB

    alerts = evaluate_health_alerts(
        data_root=tmp_path,
        recent_operations=[],
        trash_limit_mb=0,
        failure_threshold=5
    )
    assert any("Trash directory" in alert for alert in alerts)


def test_evaluate_health_alerts_failure_threshold():
    recent_ops = [{"operation": "A", "status": "failed"}, {"operation": "B", "status": "failed"}]
    alerts = evaluate_health_alerts(
        data_root=Path("."),
        recent_operations=recent_ops,
        trash_limit_mb=10240,
        failure_threshold=2
    )
    assert any("recent operation" in alert for alert in alerts)

