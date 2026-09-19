from pathlib import Path
import json
from collections import Counter


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A = PROJECT_DIR / "data" / "dataset_a"

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)

V7_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v7.jsonl"
)


SESSIONS = [
    "ses_20260701-152030-CHAITANYA0BCF",
    "ses_20260701-075548-CHAITANYA0BCF",
]


def load_jsonl(path):
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def load_raw_session(session_id):
    events = []

    for path in DATASET_A.rglob("events.jsonl"):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                if event.get("session_id") == session_id:
                    events.append(event)

    events.sort(key=lambda e: e["timestamp_ms"])

    return events


def event_types(events):
    return Counter(
        e.get("event_type", "unknown")
        for e in events
    )


def print_session(session_id, gt_records, v7_segments):
    events = load_raw_session(session_id)

    gt = [
        x for x in gt_records
        if x.get("session_id") == session_id
    ]

    pred = [
        x for x in v7_segments
        if x.get("session_id") == session_id
    ]

    print()
    print("=" * 100)
    print(session_id)
    print("=" * 100)

    print(f"Raw events       : {len(events)}")
    print(f"GT executions    : {len(gt)}")
    print(f"V7 segments      : {len(pred)}")

    print("\n--- Raw event types ---")

    for event_type, count in event_types(events).most_common():
        print(f"{event_type:30} {count}")

    print("\n--- V7 boundary types ---")

    boundaries = Counter(
        x.get("boundary_before")
        for x in pred
    )

    for boundary, count in boundaries.most_common():
        print(f"{str(boundary):40} {count}")

    print("\n--- GT execution starts ---")

    starts = Counter()

    for execution in gt:
        # Use the first event at/after the GT start.
        start_ts = execution.get("start_timestamp_ms")

        if start_ts is None:
            continue

        candidates = [
            e for e in events
            if e["timestamp_ms"] >= start_ts
        ]

        if candidates:
            starts[
                candidates[0].get("event_type", "unknown")
            ] += 1

    for event_type, count in starts.most_common():
        print(f"{event_type:30} {count}")

    print("\n--- First 10 GT executions ---")

    for i, execution in enumerate(gt[:10], 1):
        print(
            f"{i:2}. "
            f"exec={execution.get('execution_id')} "
            f"process={execution.get('process_code')} "
            f"variant={execution.get('process_variant')} "
            f"start={execution.get('start_ts')} "
            f"end={execution.get('end_ts')}"
        )

    print("\n--- First 15 V7 segments ---")

    for i, segment in enumerate(pred[:15], 1):
        print(
            f"{i:2}. "
            f"duration={segment.get('duration_seconds'):7.3f}s "
            f"events={segment.get('event_count'):3} "
            f"first={segment.get('first_event_type'):25} "
            f"last={segment.get('last_event_type'):25} "
            f"boundary={segment.get('boundary_before')}"
        )


def main():
    gt_records = load_jsonl(GT_FILE)
    v7_segments = load_jsonl(V7_FILE)

    for session_id in SESSIONS:
        print_session(
            session_id,
            gt_records,
            v7_segments
        )


if __name__ == "__main__":
    main()