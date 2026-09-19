import json
from pathlib import Path
from collections import Counter


PROJECT_DIR = Path(__file__).resolve().parents[2]

PREDICTIONS = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v3.jsonl"
)

RAW_DATASET = PROJECT_DIR / "data" / "dataset_a"


def load_predictions():
    segments = []

    with PREDICTIONS.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def load_events():
    events_by_session = {}

    for events_file in RAW_DATASET.rglob("events.jsonl"):

        with events_file.open("r", encoding="utf-8") as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get("session_id")

                if session_id is None:
                    continue

                events_by_session.setdefault(
                    session_id,
                    []
                ).append(event)

    for session_id in events_by_session:

        events_by_session[session_id].sort(
            key=lambda e: e.get("timestamp_ms", 0)
        )

    return events_by_session


def event_name(event):
    return event.get("event_type", "UNKNOWN")


def app_name(event):
    context = event.get("context", {})
    active_app = context.get("active_app", {})

    if isinstance(active_app, dict):
        return active_app.get(
            "app_name",
            active_app.get("process_name", "UNKNOWN")
        )

    return "UNKNOWN"


def main():

    print("=" * 80)
    print("DATASET A — V3 PREDICTED SEGMENT INSPECTION")
    print("=" * 80)

    segments = load_predictions()

    print(f"\nPredicted segments : {len(segments)}")

    # ------------------------------------------------------------------
    # DURATION SUMMARY
    # ------------------------------------------------------------------

    durations = [
        float(s.get("duration_seconds", 0))
        for s in segments
    ]

    durations_sorted = sorted(durations)

    print()
    print("=" * 80)
    print("DURATION SUMMARY")
    print("=" * 80)

    print(f"Minimum : {min(durations):.3f}s")
    print(f"Median  : {durations_sorted[len(durations_sorted) // 2]:.3f}s")
    print(f"Average : {sum(durations) / len(durations):.3f}s")
    print(f"Maximum : {max(durations):.3f}s")

    for threshold in [1, 2, 5, 10, 15, 30, 60]:

        count = sum(
            1 for d in durations
            if d < threshold
        )

        print(
            f"< {threshold:2d}s : "
            f"{count:5d} "
            f"({100 * count / len(durations):6.2f}%)"
        )

    # ------------------------------------------------------------------
    # SHORTEST
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("30 SHORTEST PREDICTED SEGMENTS")
    print("=" * 80)

    shortest = sorted(
        segments,
        key=lambda s: float(s.get("duration_seconds", 0))
    )[:30]

    for i, segment in enumerate(shortest, 1):

        print()
        print("-" * 80)

        print(f"{i}. {segment.get('segment_id')}")
        print(f"Session : {segment.get('session_id')}")
        print(f"Start   : {segment.get('start_timestamp_ms')}")
        print(f"End     : {segment.get('end_timestamp_ms')}")
        print(
            f"Duration: "
            f"{segment.get('duration_seconds', 0):.3f}s"
        )
        print(
            f"Events  : "
            f"{segment.get('event_count', 0)}"
        )

        print(
            f"Apps    : "
            f"{segment.get('applications', [])}"
        )

        print(
            f"First event: "
            f"{segment.get('first_event_type')}"
        )

        print(
            f"Last event : "
            f"{segment.get('last_event_type')}"
        )

    # ------------------------------------------------------------------
    # LONGEST
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("15 LONGEST PREDICTED SEGMENTS")
    print("=" * 80)

    longest = sorted(
        segments,
        key=lambda s: float(s.get("duration_seconds", 0)),
        reverse=True
    )[:15]

    for i, segment in enumerate(longest, 1):

        print()
        print("-" * 80)

        print(f"{i}. {segment.get('segment_id')}")
        print(f"Session : {segment.get('session_id')}")
        print(f"Start   : {segment.get('start_timestamp_ms')}")
        print(f"End     : {segment.get('end_timestamp_ms')}")
        print(
            f"Duration: "
            f"{segment.get('duration_seconds', 0):.3f}s"
        )
        print(
            f"Events  : "
            f"{segment.get('event_count', 0)}"
        )

        print(
            f"Apps    : "
            f"{segment.get('applications', [])}"
        )

        print(
            f"First event: "
            f"{segment.get('first_event_type')}"
        )

        print(
            f"Last event : "
            f"{segment.get('last_event_type')}"
        )

    # ------------------------------------------------------------------
    # EVENT COUNT
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("EVENT COUNT SUMMARY")
    print("=" * 80)

    event_counts = [
        int(s.get("event_count", 0))
        for s in segments
    ]

    print(f"Minimum : {min(event_counts)}")
    print(
        f"Average : "
        f"{sum(event_counts) / len(event_counts):.2f}"
    )
    print(f"Maximum : {max(event_counts)}")

    for threshold in [5, 10, 20, 50, 100]:

        count = sum(
            1 for x in event_counts
            if x < threshold
        )

        print(
            f"< {threshold:3d} events : "
            f"{count:5d} "
            f"({100 * count / len(event_counts):6.2f}%)"
        )

    # ------------------------------------------------------------------
    # FIRST / LAST EVENT PATTERNS
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("FIRST EVENT TYPES")
    print("=" * 80)

    first_events = Counter(
        s.get("first_event_type", "UNKNOWN")
        for s in segments
    )

    for event_type, count in first_events.most_common():

        print(
            f"{event_type:25s} "
            f"{count:5d} "
            f"({100 * count / len(segments):6.2f}%)"
        )

    print()
    print("=" * 80)
    print("LAST EVENT TYPES")
    print("=" * 80)

    last_events = Counter(
        s.get("last_event_type", "UNKNOWN")
        for s in segments
    )

    for event_type, count in last_events.most_common():

        print(
            f"{event_type:25s} "
            f"{count:5d} "
            f"({100 * count / len(segments):6.2f}%)"
        )


if __name__ == "__main__":
    main()