from __future__ import annotations

import csv
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import failed_file_name, file_name
from modules.helpers import APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA, make_directories, print_lg
from modules.storage import DB_PATH, DETAILS_DIR, init_db


def _archive(path: str, archive_dir: str) -> None:
    if os.path.exists(path):
        Path(archive_dir).mkdir(parents=True, exist_ok=True)
        shutil.move(path, os.path.join(archive_dir, os.path.basename(path)))
        print_lg(f"Archived {path}")


def _write_header(path: str, schema: list[str]) -> None:
    make_directories([path])
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=schema)
        writer.writeheader()


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join("all excels", "archive", timestamp)

    artifacts = [
        file_name,
        failed_file_name,
        file_name.replace(".csv", ".xlsx"),
        failed_file_name.replace(".csv", ".xlsx"),
        DB_PATH,
    ]
    for artifact in artifacts:
        _archive(artifact, archive_dir)

    if os.path.isdir(DETAILS_DIR):
        _archive(DETAILS_DIR, archive_dir)

    _write_header(file_name, APPLIED_EXPORT_SCHEMA)
    _write_header(failed_file_name, FAILED_EXPORT_SCHEMA)
    init_db()
    print_lg(f"Clean analytics baseline created. Archive: {archive_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
