"""Back up the data directory (CHUI_DATA_DIR) into a synced folder as a few compressed files.

    python scripts/backup_data.py                       # run by run_daily.cmd after the data job
    python scripts/backup_data.py --dest D:\\backup      # somewhere else
    python scripts/backup_data.py --dry-run

The data directory lives outside OneDrive because sync locks on thousands of small files and on
the live database stalled the daily job. This copies it back in a form a sync client handles well:

    <dest>/raw/<YYYY-MM-DD>.zip      every raw/<source>/<date>/ folder for that fetch date. Raw files
                                     never change, so a day's zip is written once and rewritten only
                                     if files were added to that day. Kept forever: missed fetches
                                     cannot be recovered.
    <dest>/db/chui_<YYYY-MM-DD>.sqlite.gz   consistent copy of the live database (SQLite backup
                                     API, safe while open). The newest --keep-db are kept.
    <dest>/misc.zip                  other top-level files (logs, notes); other *.sqlite files skipped.

Destination: --dest, else CHUI_BACKUP_DIR, else <OneDrive>/ChuiData_backup.
Restore: unzip every raw/*.zip and misc.zip into an empty data directory, then gunzip the newest
db/*.sqlite.gz to chui.sqlite there.
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.http import data_root  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LIVE_DB = "chui.sqlite"


def default_dest() -> Path | None:
    if os.environ.get("CHUI_BACKUP_DIR"):
        return Path(os.environ["CHUI_BACKUP_DIR"])
    onedrive = os.environ.get("OneDriveCommercial") or os.environ.get("OneDrive")
    return Path(onedrive) / "ChuiData_backup" if onedrive else None


def raw_days(src: Path) -> dict[str, list[Path]]:
    """Fetch date -> files under raw/<source>/<date>/, as paths relative to the data directory."""
    days: dict[str, list[Path]] = {}
    for day_dir in sorted((src / "raw").glob("*/*")):
        if day_dir.is_dir() and DATE.match(day_dir.name):
            files = [p.relative_to(src) for p in day_dir.rglob("*") if p.is_file()]
            days.setdefault(day_dir.name, []).extend(files)
    return days


def misc_files(src: Path) -> list[Path]:
    return sorted(p.relative_to(src) for p in src.iterdir()
                  if p.is_file() and not p.name.startswith(LIVE_DB) and p.suffix != ".sqlite")


def write_zip(src: Path, files: list[Path], target: Path, dry_run: bool) -> str:
    """Write target unless it already holds exactly these files at these sizes."""
    want = sorted((f.as_posix(), (src / f).stat().st_size) for f in files)
    if target.exists():
        try:
            with zipfile.ZipFile(target) as z:
                if sorted((i.filename, i.file_size) for i in z.infolist()) == want:
                    return "same"
        except zipfile.BadZipFile:
            pass
    if dry_run:
        return "would write"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files:
            z.write(src / f, f.as_posix())
    os.replace(tmp, target)
    return "written"


def backup_db(src: Path, dest: Path, keep: int, today: str, dry_run: bool) -> str:
    live = src / LIVE_DB
    if not live.exists():
        return "no database"
    target = dest / "db" / f"chui_{today}.sqlite.gz"
    if dry_run:
        return f"would write {target.name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    snap = src / f".{LIVE_DB}.backup"
    conn, out = sqlite3.connect(live), sqlite3.connect(snap)
    try:
        conn.backup(out)
        ok = out.execute("pragma integrity_check").fetchone()[0]
    finally:
        conn.close()
        out.close()
    if ok != "ok":
        snap.unlink()
        raise RuntimeError(f"database copy failed integrity check: {ok}")
    tmp = target.with_name(target.name + ".tmp")
    with open(snap, "rb") as f, gzip.open(tmp, "wb", compresslevel=6) as g:
        shutil.copyfileobj(f, g, 1 << 20)
    os.replace(tmp, target)
    snap.unlink()
    old = sorted((dest / "db").glob("chui_*.sqlite.gz"))[:-keep]
    for p in old:
        p.unlink()
    return f"{target.name} ({target.stat().st_size / 1e6:.1f} MB), removed {len(old)} older"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=None)
    ap.add_argument("--keep-db", type=int, default=14)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src, dest = data_root().resolve(), (args.dest or default_dest())
    if dest is None:
        sys.exit("backup: no destination (set CHUI_BACKUP_DIR or pass --dest)")
    dest = dest.resolve()
    if dest == src or src in dest.parents:
        sys.exit(f"backup: destination {dest} is inside the data directory {src}")
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"backup {src} -> {dest}")

    counts: dict[str, int] = {}
    for day, files in raw_days(src).items():
        result = write_zip(src, files, dest / "raw" / f"{day}.zip", args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if result != "same":
            print(f"  raw {day}: {result} ({len(files)} files)")
    print(f"  raw days: {counts}")
    print(f"  misc.zip: {write_zip(src, misc_files(src), dest / 'misc.zip', args.dry_run)}")
    print(f"  db: {backup_db(src, dest, args.keep_db, today, args.dry_run)}")


if __name__ == "__main__":
    main()
