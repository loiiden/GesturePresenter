"""Audit a recorded dataset before training on it.

    uv run --extra research python -m research.inspect research/data/gestures.csv

Checks that the recording actually contains the variation it was designed to
capture. Session S01 was clean by every per-frame quality measure — 99% mean
detection confidence, full-length trials — yet its near, far and offcentre
blocks were statistically indistinguishable from the normal block, because the
operator never physically moved. Nothing in the per-frame gates could see that;
only comparing conditions against each other can.

Exit status is non-zero when a condition misses its target, so this can gate a
training run.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics as st
from pathlib import Path

from research.dataset import read_rows

PROTOCOL_PATH = Path(__file__).with_name("protocol.json")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--session", action="append", default=[],
                        help="Restrict to these sessions; repeat as needed")
    return parser.parse_args(argv)


def _per_trial(rows, field: str, reducer) -> dict[tuple[str, str], float]:
    grouped: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[(row["trial_id"], row["condition"])].append(float(row[field]))
    return {key: reducer(values) for key, values in grouped.items()}


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 4], ordered[n // 2], ordered[min(n - 1, 3 * n // 4)]


def main(argv=None) -> int:
    args = parse_args(argv)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    conditions = {c["id"]: c for c in protocol["conditions"]}

    rows = read_rows(args.datasets)
    if args.session:
        rows = [row for row in rows if row["session_id"] in set(args.session)]
    if not rows:
        raise SystemExit("No rows matched the requested sessions")

    right = [row for row in rows if row["hand"] == "Right"]
    spans = _per_trial(right, "hand_span", st.median)
    margins = _per_trial(right, "edge_margin", min)

    sessions = sorted({row["session_id"] for row in rows})
    trials = len({row["trial_id"] for row in rows})
    print(f"{len(rows)} frames / {trials} trials / sessions {', '.join(sessions)}\n")

    print(f"{'condition':<11}{'n':>4}  {'span q1/med/q3':<24}{'target':<14}"
          f"{'min margin':>11}  verdict")
    failures = []
    for name, condition in conditions.items():
        values = [v for (_, c), v in spans.items() if c == name]
        if not values:
            continue
        q1, q2, q3 = _quartiles(values)
        target = condition.get("target_span")
        margin_values = [v for (_, c), v in margins.items() if c == name]
        margin_target = condition.get("target_margin_max")

        verdict, detail = "ok", ""
        if target:
            inside = sum(1 for v in values if target[0] <= v <= target[1])
            share = inside / len(values)
            if share < 0.5:
                verdict = "MISSED"
                detail = f"only {share:.0%} of trials inside the span target"
        if margin_target is not None and margin_values:
            inside = sum(1 for v in margin_values if v <= margin_target)
            if inside / len(margin_values) < 0.5:
                verdict = "MISSED"
                detail = (detail + "; " if detail else "") + \
                    f"only {inside / len(margin_values):.0%} of trials near an edge"
        if verdict == "MISSED":
            failures.append((name, detail))

        target_text = f"{target[0]:.2f}-{target[1]:.2f}" if target else "-"
        print(f"{name:<11}{len(values):>4}  "
              f"{q1:.2f} / {q2:.2f} / {q3:.2f}{'':<9}{target_text:<14}"
              f"{min(margin_values) if margin_values else 0:>11.3f}  {verdict}")

    # The decisive comparison: conditions must separate from each other, not
    # merely sit somewhere plausible on their own.
    near = [v for (_, c), v in spans.items() if c == "near"]
    far = [v for (_, c), v in spans.items() if c == "far"]
    if near and far:
        ratio = st.median(near) / st.median(far)
        print(f"\nnear/far median span ratio: {ratio:.2f}x", end="  ")
        if ratio < 1.5:
            print("← FAILED: the distance conditions did not separate")
            failures.append(("near-vs-far", f"ratio {ratio:.2f}x, expected >= 1.5x"))
        else:
            print("(good separation)")

    per_gesture = collections.Counter(
        row["gesture"] for row in {r["trial_id"]: r for r in rows}.values()
    )
    missing = [g for g in protocol["gestures"] if per_gesture[g] == 0]
    if missing:
        print(f"\nMissing gesture classes entirely: {', '.join(missing)}")
        failures.append(("coverage", f"no trials for {', '.join(missing)}"))

    if failures:
        print("\nNOT READY FOR TRAINING")
        for name, detail in failures:
            print(f"  - {name}: {detail}")
        print("\nRe-record the affected blocks. Training on this would give a "
              "model tuned to one distance and position.")
        return 1
    print("\nDataset looks usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
