import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


def parse_ts(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).timestamp() * 1000


def main():

    print("=" * 70)
    print("DATASET A — GT EXECUTION SPACING ANALYSIS")
    print("=" * 70)

    by_session = defaultdict(list)

    with GT_FILE.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            record = json.loads(line)

            by_session[
                record["session_id"]
            ].append(record)

    positive_gaps = []
    negative_gaps = []
    zero_gaps = []

    transition_flags = {
        "continues_from_prev": 0,
        "continues_to_next": 0,
        "split_id": 0,
    }

    pairs = 0

    for session_id, records in by_session.items():

        records = sorted(
            records,
            key=lambda r: parse_ts(r["start_ts"])
        )

        for record in records:

            if record.get("continues_from_prev"):
                transition_flags["continues_from_prev"] += 1

            if record.get("continues_to_next"):
                transition_flags["continues_to_next"] += 1

            if record.get("split_id") is not None:
                transition_flags["split_id"] += 1

        for previous, current in zip(
            records,
            records[1:]
        ):

            if not previous.get("end_ts"):
                continue

            previous_end = parse_ts(
                previous["end_ts"]
            )

            current_start = parse_ts(
                current["start_ts"]
            )

            gap = (
                current_start - previous_end
            ) / 1000.0

            pairs += 1

            if gap > 0:
                positive_gaps.append(gap)
            elif gap < 0:
                negative_gaps.append(gap)
            else:
                zero_gaps.append(gap)

    print()
    print(f"Sessions             : {len(by_session):,}")
    print(f"Execution pairs      : {pairs:,}")

    print()
    print("Relationship between consecutive executions")
    print("-" * 70)

    print(
        f"Positive gap        : "
        f"{len(positive_gaps):,}"
    )

    print(
        f"Zero gap            : "
        f"{len(zero_gaps):,}"
    )

    print(
        f"Overlapping         : "
        f"{len(negative_gaps):,}"
    )

    if positive_gaps:

        values = sorted(positive_gaps)

        print()
        print("Positive gap statistics")
        print("-" * 70)

        print(
            f"Minimum : "
            f"{min(values):.4f}s"
        )

        print(
            f"Median  : "
            f"{statistics.median(values):.4f}s"
        )

        print(
            f"Mean    : "
            f"{statistics.mean(values):.4f}s"
        )

        for threshold in [
            0.1,
            0.25,
            0.5,
            1,
            2,
            3,
            5,
            8,
            10,
            15,
            30,
        ]:

            count = sum(
                1
                for value in values
                if value > threshold
            )

            percentage = (
                100 * count / len(values)
            )

            print(
                f"> {threshold:>5g}s : "
                f"{count:>6,} "
                f"({percentage:6.2f}%)"
            )

    print()
    print("GT continuation / split metadata")
    print("-" * 70)

    for key, value in transition_flags.items():

        print(
            f"{key:25s}: "
            f"{value:,}"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()