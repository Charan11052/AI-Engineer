import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


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


def get_app(event):
    context = event.get("context") or {}
    active_app = context.get("active_app") or {}
    return active_app.get("app_name")


def get_window(event):
    context = event.get("context") or {}
    active_app = context.get("active_app") or {}
    return active_app.get("window_title")


def has_text(event):
    payload = event.get("payload") or {}
    metadata = event.get("metadata") or {}

    text_candidates = [
        payload.get("text"),
        payload.get("extracted_text"),
        metadata.get("text"),
        metadata.get("extracted_text"),
    ]

    return any(
        isinstance(value, str) and value.strip()
        for value in text_candidates
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

                if session_id is None:
                    continue

                if timestamp_ms is None:
                    continue

                event["_timestamp_ms"] = int(timestamp_ms)

                events_by_session[
                    session_id
                ].append(event)

    for session_id in events_by_session:

        events_by_session[session_id].sort(
            key=lambda event: event["_timestamp_ms"]
        )

    return events_by_session


def load_gt():

    records = []

    with GT_FILE.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            records.append(json.loads(line))

    return records


def main():

    print("=" * 100)
    print("DATASET A — RAW EVENT SEQUENCES AROUND GT BOUNDARIES")
    print("=" * 100)

    events_by_session = load_events()
    gt_records = load_gt()

    shown = 0

    for gt in gt_records:

        if shown >= 10:
            break

        start_ts = gt.get("start_ts")

        if not start_ts:
            continue

        session_id = gt["session_id"]

        events = events_by_session.get(session_id)

        if not events:
            continue

        start_ms = parse_ts(start_ts)

        # Find first event at or after GT start.
        boundary_index = None

        for i, event in enumerate(events):

            if event["_timestamp_ms"] >= start_ms:

                boundary_index = i
                break

        if boundary_index is None:
            continue

        print()
        print("=" * 100)

        print(
            f"GT EXECUTION {shown + 1}"
        )

        print(
            f"Execution ID : {gt.get('execution_id')}"
        )

        print(
            f"Process      : {gt.get('process_code')}"
        )

        print(
            f"Variant      : {gt.get('process_variant')}"
        )

        print(
            f"Case         : {gt.get('case_id')}"
        )

        print(
            f"Session      : {session_id}"
        )

        print(
            f"GT start     : {gt.get('start_ts')}"
        )

        print(
            f"GT end       : {gt.get('end_ts')}"
        )

        print(
            f"continues_from_prev: "
            f"{gt.get('continues_from_prev')}"
        )

        print(
            f"continues_to_next: "
            f"{gt.get('continues_to_next')}"
        )

        print(
            f"split_id: {gt.get('split_id')}"
        )

        print("-" * 100)

        start = max(
            0,
            boundary_index - 10
        )

        end = min(
            len(events),
            boundary_index + 11
        )

        previous_ts = None

        for i in range(start, end):

            event = events[i]

            timestamp = event["_timestamp_ms"]

            if previous_ts is None:
                gap = 0
            else:
                gap = (
                    timestamp - previous_ts
                ) / 1000.0

            marker = (
                "<<< GT START"
                if i == boundary_index
                else ""
            )

            print(
                f"{i:8d} | "
                f"{timestamp} | "
                f"gap={gap:8.4f}s | "
                f"{event.get('event_type', '')[:25]:25s} | "
                f"{str(get_app(event))[:22]:22s} | "
                f"text={str(has_text(event)):5s} | "
                f"{marker}"
            )

            previous_ts = timestamp

        shown += 1

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()