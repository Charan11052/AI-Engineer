import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A = PROJECT_DIR / "data" / "dataset_a"

OUTPUT_DIR = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "dataset_a_predicted_segments_v5.jsonl"
)


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

# Very long inactivity is still a reliable session/activity boundary.
HARD_GAP_SECONDS = 20.0

# A screenshot followed by a strong activity event is a
# candidate transaction boundary.
SCREENSHOT_TRANSITION_MAX_GAP_SECONDS = 10.0

# Do not split extremely small fragments.
MIN_EVENTS_BEFORE_BOUNDARY = 10

MIN_DURATION_BEFORE_BOUNDARY_SECONDS = 3.0


START_EVENTS = {
    "app_switch",
    "browser_navigation",
    "mouse_click",
    "browser_click",
    "upload_completed",
}


IGNORED_EVENTS = {
    "session_start",
    "session_ended",
}


CHECKPOINT_EVENT = "screenshot_smart"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def timestamp_iso(timestamp_ms):
    dt = datetime.fromtimestamp(
        timestamp_ms / 1000.0,
        tz=timezone.utc
    )

    return dt.isoformat()


def get_app(event):
    context = event.get("context", {})

    active_app = context.get(
        "active_app",
        {}
    )

    if not isinstance(active_app, dict):
        return None

    return (
        active_app.get("app_name")
        or active_app.get("process_name")
    )


def load_events():
    sessions = {}

    for events_file in DATASET_A.rglob("events.jsonl"):

        with events_file.open(
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

                timestamp_ms = event.get(
                    "timestamp_ms"
                )

                if (
                    session_id is None
                    or timestamp_ms is None
                ):
                    continue

                sessions.setdefault(
                    session_id,
                    []
                ).append(event)

    for session_id in sessions:

        sessions[session_id].sort(
            key=lambda e: e["timestamp_ms"]
        )

    return sessions


# ----------------------------------------------------------------------
# Segment creation
# ----------------------------------------------------------------------

def create_segment(
    session_id,
    segment_number,
    events,
    boundary_reason
):

    start_ms = events[0]["timestamp_ms"]
    end_ms = events[-1]["timestamp_ms"]

    duration_seconds = (
        end_ms - start_ms
    ) / 1000.0

    apps = sorted(
        {
            app
            for event in events
            if (app := get_app(event)) is not None
        }
    )

    event_types = Counter(
        event.get(
            "event_type",
            "unknown"
        )
        for event in events
    )

    return {
        "session_id": session_id,

        "segment_id": (
            f"{session_id}"
            f"-SEG-{segment_number:04d}"
        ),

        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,

        "start_timestamp": timestamp_iso(
            start_ms
        ),

        "end_timestamp": timestamp_iso(
            end_ms
        ),

        "duration_seconds": round(
            duration_seconds,
            3
        ),

        "event_count": len(events),

        "apps": apps,

        "event_types": dict(
            event_types
        ),

        "first_event_type": events[0].get(
            "event_type"
        ),

        "last_event_type": events[-1].get(
            "event_type"
        ),

        "boundary_before": boundary_reason,
    }


# ----------------------------------------------------------------------
# Boundary detection
# ----------------------------------------------------------------------

def should_split(
    previous_event,
    current_event,
    current_segment,
    last_screenshot
):

    previous_ts = previous_event["timestamp_ms"]
    current_ts = current_event["timestamp_ms"]

    gap_seconds = (
        current_ts - previous_ts
    ) / 1000.0

    current_event_type = current_event.get(
        "event_type"
    )

    segment_event_count = len(
        current_segment
    )

    segment_duration = (
        current_segment[-1]["timestamp_ms"]
        - current_segment[0]["timestamp_ms"]
    ) / 1000.0

    # --------------------------------------------------------------
    # Rule 1: hard inactivity boundary
    # --------------------------------------------------------------

    if gap_seconds >= HARD_GAP_SECONDS:

        return True, "hard_gap"


    # --------------------------------------------------------------
    # Rule 2: screenshot -> strong activity transition
    # --------------------------------------------------------------

    if (
        last_screenshot is not None
        and current_event_type in START_EVENTS
    ):

        screenshot_ts = (
            last_screenshot["timestamp_ms"]
        )

        screenshot_to_current = (
            current_ts - screenshot_ts
        ) / 1000.0

        if (
            0 <= screenshot_to_current
            <= SCREENSHOT_TRANSITION_MAX_GAP_SECONDS
        ):

            meaningful_segment = (
                segment_event_count
                >= MIN_EVENTS_BEFORE_BOUNDARY
                or
                segment_duration
                >= MIN_DURATION_BEFORE_BOUNDARY_SECONDS
            )

            if meaningful_segment:

                return (
                    True,
                    "screenshot_to_activity_transition"
                )


    return False, None


# ----------------------------------------------------------------------
# Session segmentation
# ----------------------------------------------------------------------

def segment_session(
    session_id,
    events
):

    activity_events = [
        event
        for event in events
        if event.get("event_type")
        not in IGNORED_EVENTS
    ]

    if not activity_events:
        return []

    segments = []

    current_segment = [
        activity_events[0]
    ]

    boundary_reason = "session_start"

    last_screenshot = None

    for i in range(
        1,
        len(activity_events)
    ):

        previous_event = (
            activity_events[i - 1]
        )

        current_event = (
            activity_events[i]
        )

        split, reason = should_split(
            previous_event,
            current_event,
            current_segment,
            last_screenshot
        )

        if split:

            segments.append(
                create_segment(
                    session_id,
                    len(segments) + 1,
                    current_segment,
                    boundary_reason
                )
            )

            current_segment = [
                current_event
            ]

            boundary_reason = reason

            last_screenshot = None

        else:

            current_segment.append(
                current_event
            )

        # Update checkpoint after processing
        # the current event.
        if (
            current_event.get("event_type")
            == CHECKPOINT_EVENT
        ):
            last_screenshot = current_event

    if current_segment:

        segments.append(
            create_segment(
                session_id,
                len(segments) + 1,
                current_segment,
                boundary_reason
            )
        )

    return segments


# ----------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------

def print_statistics(segments):

    if not segments:
        print("No segments generated.")
        return

    durations = [
        s["duration_seconds"]
        for s in segments
    ]

    event_counts = [
        s["event_count"]
        for s in segments
    ]

    print()
    print("Segment statistics")
    print("-" * 70)

    print(
        f"Minimum duration : "
        f"{min(durations):.2f}s"
    )

    print(
        f"Median duration  : "
        f"{sorted(durations)[len(durations)//2]:.2f}s"
    )

    print(
        f"Maximum duration : "
        f"{max(durations):.2f}s"
    )

    print(
        f"Average duration : "
        f"{sum(durations) / len(durations):.2f}s"
    )

    print(
        f"Average events   : "
        f"{sum(event_counts) / len(event_counts):.2f}"
    )

    print()
    print("Duration buckets")
    print("-" * 70)

    buckets = [
        ("< 5s", lambda x: x < 5),
        ("5–15s", lambda x: 5 <= x < 15),
        ("15–30s", lambda x: 15 <= x < 30),
        ("30–60s", lambda x: 30 <= x < 60),
        (">= 60s", lambda x: x >= 60),
    ]

    for label, predicate in buckets:

        count = sum(
            1
            for duration in durations
            if predicate(duration)
        )

        percentage = (
            100 * count / len(durations)
        )

        print(
            f"{label:8s}: "
            f"{count:6d} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("Boundary reasons")
    print("-" * 70)

    reasons = Counter(
        s["boundary_before"]
        for s in segments
    )

    for reason, count in reasons.items():

        print(
            f"{reason:40s}: "
            f"{count:6d}"
        )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def main():

    print("=" * 70)
    print("DATASET A — INDEPENDENT SEGMENTATION V5")
    print("=" * 70)

    sessions = load_events()

    total_events = sum(
        len(events)
        for events in sessions.values()
    )

    print()
    print(
        f"Sessions loaded : "
        f"{len(sessions)}"
    )

    print(
        f"Events loaded   : "
        f"{total_events}"
    )

    all_segments = []

    for session_id, events in sessions.items():

        segments = segment_session(
            session_id,
            events
        )

        all_segments.extend(
            segments
        )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for segment in all_segments:

            f.write(
                json.dumps(
                    segment,
                    ensure_ascii=False
                )
                + "\n"
            )

    print(
        f"Predicted segments: "
        f"{len(all_segments)}"
    )

    print(
        f"Output: "
        f"{OUTPUT_FILE}"
    )

    print_statistics(
        all_segments
    )


if __name__ == "__main__":
    main()