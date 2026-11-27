"""File writer for event export (CSV / JSON)."""

from __future__ import annotations

import csv
import json
from pathlib import Path


class FileEventExporter:
    """Implements ``EventExporter``."""

    def exists(self, path: str) -> bool:
        """True if the file exists."""
        return Path(path).expanduser().exists()

    def write(self, path: str, rows: list[dict[str, object]], fmt: str) -> None:
        """Write rows; parent directory must exist."""
        target = Path(path).expanduser()
        if not target.parent.is_dir():
            raise ValueError(f"Directory {target.parent} does not exist.")
        if fmt == "json":
            target.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
            return
        fields = [
            "id",
            "timestamp",
            "severity",
            "category",
            "device",
            "message",
            "payload",
        ]
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {k: json.dumps(v) if k == "payload" else v for k, v in row.items()}
                )
