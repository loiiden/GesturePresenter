"""Retain unchanged recordings and replace point, pinch and pinch_right.

Writes a fresh working CSV and migration report. The original recordings stay
intact for recovery. Record clean point and index_thumb trials separately.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from research.dataset import COLUMNS, read_rows, summarize

RETIRED = frozenset({"pinch", "pinch_right"})
REPLACED = RETIRED | {"point"}


def partition_rows(rows: list[dict]):
    """Remove the three old labels without inspecting or relabelling poses."""
    kept = [r for r in rows if r["gesture"] not in REPLACED]
    removed = [r for r in rows if r["gesture"] in REPLACED]
    return kept, removed


def write_csv(path: Path, rows: list[dict]) -> None:
    """Create a new file, never append duplicate rows or overwrite recordings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path("research/data/gestures_v3.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    rows = read_rows(args.datasets)
    kept, removed = partition_rows(rows)
    report_path = args.output.with_suffix(".migration.json")
    report = {
        "sources": [str(p) for p in args.datasets], "output": str(args.output),
        "removed_labels": sorted(REPLACED),
        "record_next": ["point", "index_thumb"],
        "original": summarize(rows), "retained": summarize(kept),
        "removed": summarize(removed),
    }
    for name in ("original", "retained", "removed"):
        stats = report[name]
        print(f"{name}: {stats['frames']} frames / {stats['trials']} trials")
    if args.dry_run:
        return
    if any(p.exists() for p in (args.output, report_path)):
        raise SystemExit("An output already exists; choose a new --output. Nothing overwritten.")
    write_csv(args.output, kept)
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"Working dataset: {args.output}\nReport: {report_path}")
    print("Original recordings preserved. Record point and index_thumb before training.")


if __name__ == "__main__":
    main()
