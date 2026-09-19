import json
from pathlib import Path
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A_DIR = (
    PROJECT_DIR
    / "data"
    / "dataset_a"
)


def load_event_gaps():

    all_gaps = []

    event_files = sorted(
        DATASET_A_DIR.rglob(
            "events.jsonl"
        )
    )

    print(
        f"Found {len(event_files)} "
        f"events.jsonl files."
    )

    for event_file in event_files:

        previous_timestamp = None

        with event_file.open(
            "r",
            encoding="utf-8",
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                timestamp = event.get(
                    "timestamp_ms"
                )

                if timestamp is None:
                    continue

                timestamp = int(timestamp)

                if previous_timestamp is not None:

                    gap = (
                        timestamp
                        - previous_timestamp
                    ) / 1000.0

                    if gap >= 0:
                        all_gaps.append(gap)

                previous_timestamp = timestamp

    return all_gaps


def percentile(sorted_values, p):

    if not sorted_values:
        return None

    index = (
        (len(sorted_values) - 1)
        * p
    )

    lower = int(index)

    upper = min(
        lower + 1,
        len(sorted_values) - 1,
    )

    fraction = index - lower

    return (
        sorted_values[lower]
        + fraction
        * (
            sorted_values[upper]
            - sorted_values[lower]
        )
    )


def main():

    print("=" * 70)
    print(
        "DATASET A — RAW EVENT GAP ANALYSIS"
    )
    print("=" * 70)

    gaps = load_event_gaps()

    if not gaps:

        print("No gaps found.")

        return

    gaps.sort()

    print()
    print(
        f"Total event gaps: "
        f"{len(gaps):,}"
    )

    print()
    print("Gap distribution")
    print("-" * 70)

    print(
        f"Minimum : "
        f"{gaps[0]:.4f}s"
    )

    print(
        f"Median  : "
        f"{statistics.median(gaps):.4f}s"
    )

    print(
        f"Mean    : "
        f"{statistics.mean(gaps):.4f}s"
    )

    print(
        f"P75     : "
        f"{percentile(gaps, 0.75):.4f}s"
    )

    print(
        f"P90     : "
        f"{percentile(gaps, 0.90):.4f}s"
    )

    print(
        f"P95     : "
        f"{percentile(gaps, 0.95):.4f}s"
    )

    print(
        f"P97.5   : "
        f"{percentile(gaps, 0.975):.4f}s"
    )

    print(
        f"P99     : "
        f"{percentile(gaps, 0.99):.4f}s"
    )

    print(
        f"P99.5   : "
        f"{percentile(gaps, 0.995):.4f}s"
    )

    print(
        f"P99.9   : "
        f"{percentile(gaps, 0.999):.4f}s"
    )

    print(
        f"Maximum : "
        f"{gaps[-1]:.4f}s"
    )

    print()
    print("Long-gap counts")
    print("-" * 70)

    thresholds = [
        1,
        2,
        3,
        5,
        8,
        10,
        15,
        20,
        30,
        60,
    ]

    for threshold in thresholds:

        count = sum(
            1
            for gap in gaps
            if gap > threshold
        )

        percentage = (
            100
            * count
            / len(gaps)
        )

        print(
            f"> {threshold:>2}s : "
            f"{count:>7,} "
            f"({percentage:.3f}%)"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()