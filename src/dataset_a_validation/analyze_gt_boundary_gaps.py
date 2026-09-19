import json
from pathlib import Path
from collections import defaultdict
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A_DIR = (
    PROJECT_DIR
    / "data"
    / "dataset_a"
)

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


def load_raw_events():

    events_by_session = defaultdict(list)

    files = sorted(
        DATASET_A_DIR.rglob(
            "events.jsonl"
        )
    )

    for path in files:

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get(
                    "session_id"
                )

                timestamp = event.get(
                    "timestamp_ms"
                )

                if (
                    session_id is None
                    or timestamp is None
                ):
                    continue

                events_by_session[
                    session_id
                ].append(
                    event
                )

    for session_id in events_by_session:

        events_by_session[
            session_id
        ].sort(
            key=lambda e:
                int(e["timestamp_ms"])
        )

    return events_by_session


def load_gt():

    records = []

    with GT_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            records.append(
                json.loads(line)
            )

    return records


def nearest_previous_gap(
    events,
    timestamp_ms
):
    """
    Find the raw event immediately before the GT
    boundary and return the gap to the boundary.

    Also return the previous event metadata.
    """

    previous = None

    for event in events:

        event_ts = int(
            event["timestamp_ms"]
        )

        if event_ts >= timestamp_ms:
            break

        previous = event

    if previous is None:
        return None

    previous_ts = int(
        previous["timestamp_ms"]
    )

    gap = (
        timestamp_ms
        - previous_ts
    ) / 1000.0

    return gap, previous


def main():

    print("=" * 70)
    print(
        "DATASET A — "
        "GT BOUNDARY / RAW GAP ANALYSIS"
    )
    print("=" * 70)

    events_by_session = (
        load_raw_events()
    )

    gt_records = load_gt()

    boundary_gaps = []

    valid_boundaries = 0

    missing_session = 0

    no_previous_event = 0

    for gt in gt_records:

        start_ts = gt.get(
            "start_ts"
        )

        if not start_ts:
            continue

        session_id = gt.get(
            "session_id"
        )

        if session_id not in events_by_session:

            missing_session += 1

            continue

        # Convert ISO timestamp to milliseconds.
        from datetime import datetime

        start_ms = int(
            datetime.fromisoformat(
                start_ts.replace(
                    "Z",
                    "+00:00"
                )
            ).timestamp()
            * 1000
        )

        result = nearest_previous_gap(
            events_by_session[
                session_id
            ],
            start_ms
        )

        if result is None:

            no_previous_event += 1

            continue

        gap, previous_event = result

        boundary_gaps.append(
            {
                "gap": gap,
                "event_type":
                    previous_event.get(
                        "event_type"
                    ),
                "layer":
                    previous_event.get(
                        "layer"
                    ),
                "app":
                    (
                        previous_event
                        .get("context", {})
                        .get("active_app", {})
                        or {}
                    ).get(
                        "app_name"
                    ),
            }
        )

        valid_boundaries += 1

    gaps = sorted(
        x["gap"]
        for x in boundary_gaps
    )

    print()
    print(
        f"GT records: "
        f"{len(gt_records):,}"
    )

    print(
        f"GT boundaries analyzed: "
        f"{valid_boundaries:,}"
    )

    print(
        f"Missing sessions: "
        f"{missing_session:,}"
    )

    print(
        f"No previous event: "
        f"{no_previous_event:,}"
    )

    if not gaps:

        print("No boundary gaps found.")

        return

    print()
    print("Gap immediately before GT start")
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

    def percentile(values, p):

        index = (
            (len(values) - 1)
            * p
        )

        lower = int(index)

        upper = min(
            lower + 1,
            len(values) - 1
        )

        fraction = (
            index - lower
        )

        return (
            values[lower]
            + fraction
            * (
                values[upper]
                - values[lower]
            )
        )

    for p in [
        0.75,
        0.90,
        0.95,
        0.975,
        0.99,
    ]:

        print(
            f"P{p * 100:g}    : "
            f"{percentile(gaps, p):.4f}s"
        )

    print(
        f"Maximum : "
        f"{gaps[-1]:.4f}s"
    )

    print()
    print(
        "GT boundary gap buckets"
    )

    print("-" * 70)

    thresholds = [
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
            f"> {threshold:>5g}s : "
            f"{count:>6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print(
        "Previous event types before GT starts"
    )

    print("-" * 70)

    event_type_counts = defaultdict(int)

    for item in boundary_gaps:

        event_type_counts[
            item["event_type"]
        ] += 1

    for event_type, count in sorted(
        event_type_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:15]:

        percentage = (
            100
            * count
            / len(boundary_gaps)
        )

        print(
            f"{event_type:30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()