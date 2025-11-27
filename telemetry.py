from pathlib import Path
from typing import Dict, Iterable, List


def get_directory_size_mb(directory: Path) -> float:
    """Calculate the total size of a directory in megabytes."""
    if not directory.exists():
        return 0.0

    total_bytes = 0
    for path in directory.rglob("*"):
        if path.is_file():
            try:
                total_bytes += path.stat().st_size
            except (OSError, FileNotFoundError):
                continue
    return total_bytes / (1024 * 1024)


def evaluate_health_alerts(
    data_root: Path,
    recent_operations: Iterable[Dict[str, str]],
    *,
    trash_limit_mb: int,
    failure_threshold: int
) -> List[str]:
    """Return a list of telemetry alerts to display in the UI."""
    alerts: List[str] = []
    trash_dir = data_root / "trash"

    size_mb = get_directory_size_mb(trash_dir)
    if size_mb >= trash_limit_mb:
        alerts.append(
            f"⚠️ Trash directory is {size_mb:.1f} MB, exceeding the {trash_limit_mb} MB threshold."
        )

    failure_count = sum(
        1 for entry in recent_operations if entry.get("status", "").lower() != "success"
    )
    if failure_count >= failure_threshold:
        alerts.append(
            f"⚠️ {failure_count} recent operation(s) failed. Check logs or retry the last action."
        )

    return alerts

