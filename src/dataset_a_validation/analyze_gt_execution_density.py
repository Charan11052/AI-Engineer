import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A_DIR = PROJECT_DIR / "data" / "dataset_a"

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


def parse_ts(value):
    return int(
        datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp() * 1000
    )


def load_events():

    events_by_session = defaultdict(list)

    for path in sorted(
        DATASET_A_DIR.rglob("events.jsonl")
    ):

        with path.open("r", encoding="utf-8") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get("session_id")
                timestamp_ms = event.get("timestamp_ms")

                if session_id is None or timestamp_ms is None:
                    continue

                event["_timestamp_ms"] = int(timestamp_ms)

                events_by_session[
                    session_id
                ].append(event)

    for session_id in events_by_session:

        events_by_session[session_id].sort(
            key=lambda e: e["_timestamp_ms"]
        )

    return events_by_session


def load_gt():

    records = []

    with GT_FILE.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def count_events(events):

    counts = Counter(
        event.get("event_type")
        for event in events
    )

    return counts


def main():

    print("=" * 70)
    print("DATASET A — GT EXECUTION DENSITY ANALYSIS")
    print("=" * 70)

    events_by_session = load_events()
    gt_records = load_gt()

    rows = []

    for gt in gt_records:

        if not gt.get("start_ts") or not gt.get("end_ts"):
            continue

        session_id = gt["session_id"]

        events = events_by_session.get(session_id)

        if not events:
            continue

        start_ms = parse_ts(gt["start_ts"])
        end_ms = parse_ts(gt["end_ts"])

        duration = (
            end_ms - start_ms
        ) / 1000.0

        inside = [
            event
            for event in events
            if start_ms <= event["_timestamp_ms"] <= end_ms
        ]

        if not inside:
            continue

        counts = count_events(inside)

        rows.append({
            "execution_id": gt.get("execution_id"),
            "process": gt.get("process_code"),
            "duration": duration,
            "events": len(inside),
            "density": (
                len(inside) / duration
                if duration > 0
                else 0
            ),
            "screenshots": counts["screenshot_smart"],
            "app_switch": counts["app_switch"],
            "mouse_click": counts["mouse_click"],
            "browser_click": counts["browser_click"],
            "keystroke": counts["keystroke"],
            "shortcut": counts["shortcut"],
            "first_event": inside[0].get("event_type"),
            "last_event": inside[-1].get("event_type"),
        })

    print()
    print(f"GT records with valid intervals: {len(rows):,}")

    if not rows:
        return

    # --------------------------------------------------------
    # Aggregate statistics
    # --------------------------------------------------------

    def stats(name, values):

        values = sorted(values)

        print()
        print(name)
        print("-" * 70)

        print(
            f"Minimum : {min(values):.4f}"
        )

        print(
            f"Median  : {statistics.median(values):.4f}"
        )

        print(
            f"Mean    : {statistics.mean(values):.4f}"
        )

        print(
            f"Maximum : {max(values):.4f}"
        )

    stats(
        "Execution duration (seconds)",
        [r["duration"] for r in rows],
    )

    stats(
        "Events per execution",
        [r["events"] for r in rows],
    )

    stats(
        "Event density (events / second)",
        [r["density"] for r in rows],
    )

    stats(
        "Screenshots per execution",
        [r["screenshots"] for r in rows],
    )

    stats(
        "App switches per execution",
        [r["app_switch"] for r in rows],
    )

    stats(
        "Mouse clicks per execution",
        [r["mouse_click"] for r in rows],
    )

    stats(
        "Keystrokes per execution",
        [r["keystroke"] for r in rows],
    )

    # --------------------------------------------------------
    # First and last event types
    # --------------------------------------------------------

    print()
    print("First event inside GT execution")
    print("-" * 70)

    first_counts = Counter(
        r["first_event"]
        for r in rows
    )

    for event_type, count in first_counts.most_common(15):

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({100 * count / len(rows):6.2f}%)"
        )

    print()
    print("Last event inside GT execution")
    print("-" * 70)

    last_counts = Counter(
        r["last_event"]
        for r in rows
    )

    for event_type, count in last_counts.most_common(15):

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({100 * count / len(rows):6.2f}%)"
        )

    # --------------------------------------------------------
    # Very short / very long executions
    # --------------------------------------------------------

    print()
    print("Shortest executions")
    print("-" * 70)

    for row in sorted(
        rows,
        key=lambda r: r["duration"]
    )[:10]:

        print(
            f"{row['execution_id']:12s} "
            f"process={row['process']:2s} "
            f"duration={row['duration']:7.2f}s "
            f"events={row['events']:4d} "
            f"density={row['density']:7.2f}"
        )

    print()
    print("Longest executions")
    print("-" * 70)

    for row in sorted(
        rows,
        key=lambda r: r["duration"],
        reverse=True
    )[:10]:

        print(
            f"{row['execution_id']:12s} "
            f"process={row['process']:2s} "
            f"duration={row['duration']:7.2f}s "
            f"events={row['events']:4d} "
            f"density={row['density']:7.2f}"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()