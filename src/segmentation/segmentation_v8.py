from pathlib import Path
import json
from datetime import datetime


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A = PROJECT_DIR / "data" / "dataset_a"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"

OUTPUT_FILE = OUTPUT_DIR / "dataset_a_predicted_segments_v8.jsonl"


# ============================================================
# CONFIGURATION
# ============================================================

HARD_GAP_SECONDS = 20.0

# Candidate transition must be close to a screenshot.
SCREENSHOT_TRANSITION_MAX_GAP_SECONDS = 3.0

# A segment must contain enough activity before we allow
# an internal transition to split it.
MIN_EVENTS_BEFORE_BOUNDARY = 35
MIN_DURATION_BEFORE_BOUNDARY_SECONDS = 20.0

# Activity after the transition.
RECENT_ACTIVITY_WINDOW_SECONDS = 4.0
MIN_RECENT_ACTIVITY = 5

# Collapse repeated app_switch events into one transition burst.
TRANSITION_BURST_SECONDS = 1.5

START_EVENTS = {
    "app_switch",
    "browser_navigation",
    "mouse_click",
}

ACTIVITY_EVENTS = {
    "app_switch",
    "browser_navigation",
    "mouse_click",
    "browser_click",
    "keystroke",
    "shortcut",
    "clipboard_change",
    "upload_completed",
    "mouse_scroll",
}

IGNORED_EVENTS = {
    "session_start",
    "session_ended",
}


# ============================================================
# HELPERS
# ============================================================

def parse_timestamp(event):
    """
    Return event timestamp in milliseconds.

    timestamp_ms is preferred because it is already numeric.
    """
    value = event.get("timestamp_ms")

    if value is not None:
        return float(value)

    ts = event.get("timestamp_iso")

    if not ts:
        return None

    return (
        datetime.fromisoformat(
            ts.replace("Z", "+00:00")
        ).timestamp()
        * 1000
    )


def get_app(event):
    """
    Return active application identity from event context.
    """
    context = event.get("context") or {}
    app = context.get("active_app") or {}

    return (
        app.get("app_name"),
        app.get("process_name"),
        app.get("process_id"),
        app.get("window_title"),
    )


def get_payload_app(event, key):
    """
    Return application identity from app_switch payload.

    This is more reliable for detecting an actual transition
    than relying only on context.active_app.
    """
    payload = event.get("payload") or {}
    app = payload.get(key) or {}

    return (
        app.get("app_name"),
        app.get("process_name"),
        app.get("process_id"),
        app.get("window_title"),
    )


def is_real_app_transition(event):
    """
    Determine whether an app_switch event represents an
    actual identity change.
    """
    if event.get("event_type") != "app_switch":
        return False

    previous = get_payload_app(
        event,
        "previous_app"
    )

    new = get_payload_app(
        event,
        "new_app"
    )

    return previous != new


def get_event_type(event):
    return event.get("event_type")


def count_recent_activity(
    events,
    current_index,
    window_seconds=RECENT_ACTIVITY_WINDOW_SECONDS,
):
    """
    Count meaningful activity events immediately following
    a candidate boundary.
    """
    current_ts = parse_timestamp(
        events[current_index]
    )

    if current_ts is None:
        return 0

    count = 0

    for j in range(
        current_index + 1,
        len(events),
    ):
        ts = parse_timestamp(events[j])

        if ts is None:
            continue

        elapsed = (ts - current_ts) / 1000.0

        if elapsed > window_seconds:
            break

        if get_event_type(events[j]) in ACTIVITY_EVENTS:
            count += 1

    return count


def transition_is_burst_start(
    events,
    current_index,
):
    """
    Return True only for the first meaningful transition
    in a rapid transition burst.

    This prevents repeated app_switch events from creating
    multiple boundaries.
    """
    current_ts = parse_timestamp(
        events[current_index]
    )

    if current_ts is None:
        return False

    for j in range(
        current_index - 1,
        -1,
        -1,
    ):
        event = events[j]

        if event.get("event_type") != "app_switch":
            continue

        previous_ts = parse_timestamp(event)

        if previous_ts is None:
            continue

        gap = (current_ts - previous_ts) / 1000.0

        if gap > TRANSITION_BURST_SECONDS:
            break

        if is_real_app_transition(event):
            return False

    return True


def get_last_screenshot_timestamp(
    events,
    current_index,
):
    """
    Find the most recent screenshot before current event.
    """
    for j in range(
        current_index - 1,
        -1,
        -1,
    ):
        if (
            events[j].get("event_type")
            == "screenshot_smart"
        ):
            return parse_timestamp(events[j])

    return None


def should_split(
    events,
    current_index,
    segment_start_index,
    last_screenshot_ts,
):
    """
    Evidence-based boundary decision.

    Returns:
        (True/False, reason)
    """

    current = events[current_index]

    current_ts = parse_timestamp(current)

    if current_ts is None:
        return False, None

    # --------------------------------------------------------
    # 1. HARD INACTIVITY GAP
    # --------------------------------------------------------

    if current_index > segment_start_index:

        previous_ts = parse_timestamp(
            events[current_index - 1]
        )

        if previous_ts is not None:

            gap = (
                current_ts - previous_ts
            ) / 1000.0

            if gap >= HARD_GAP_SECONDS:
                return True, "hard_gap"

    event_type = get_event_type(current)

    # --------------------------------------------------------
    # 2. ONLY START EVENTS CAN CREATE INTERNAL BOUNDARIES
    # --------------------------------------------------------

    if event_type not in START_EVENTS:
        return False, None

    # Segment maturity.
    segment_events = (
        current_index - segment_start_index
    )

    if segment_events < MIN_EVENTS_BEFORE_BOUNDARY:
        return False, None

    segment_start_ts = parse_timestamp(
        events[segment_start_index]
    )

    if segment_start_ts is None:
        return False, None

    segment_duration = (
        current_ts - segment_start_ts
    ) / 1000.0

    if (
        segment_duration
        < MIN_DURATION_BEFORE_BOUNDARY_SECONDS
    ):
        return False, None

    # --------------------------------------------------------
    # 3. REAL APP/WINDOW TRANSITION
    # --------------------------------------------------------

    real_transition = (
        event_type == "app_switch"
        and is_real_app_transition(current)
    )

    # --------------------------------------------------------
    # 4. SCREENSHOT + REAL TRANSITION
    # --------------------------------------------------------

    if real_transition:

        if not transition_is_burst_start(
            events,
            current_index,
        ):
            return False, None

        if last_screenshot_ts is None:
            return False, None

        screenshot_gap = (
            current_ts - last_screenshot_ts
        ) / 1000.0

        if (
            screenshot_gap
            <= SCREENSHOT_TRANSITION_MAX_GAP_SECONDS
        ):

            recent_activity = count_recent_activity(
                events,
                current_index,
            )

            if recent_activity >= MIN_RECENT_ACTIVITY:

                return True, (
                    "screenshot_real_transition"
                )

    # --------------------------------------------------------
    # 5. NAVIGATION / CLICK AFTER SCREENSHOT
    # --------------------------------------------------------

    if event_type in {
        "browser_navigation",
        "mouse_click",
    }:

        if last_screenshot_ts is None:
            return False, None

        screenshot_gap = (
            current_ts - last_screenshot_ts
        ) / 1000.0

        if (
            screenshot_gap
            <= SCREENSHOT_TRANSITION_MAX_GAP_SECONDS
        ):

            recent_activity = count_recent_activity(
                events,
                current_index,
            )

            if recent_activity >= MIN_RECENT_ACTIVITY:

                return True, (
                    "screenshot_activity_transition"
                )

    return False, None


# ============================================================
# SEGMENT CREATION
# ============================================================

def create_segment(
    session_id,
    events,
    start_index,
    end_index,
    boundary_reason,
    segment_number,
):
    segment_events = events[
        start_index:end_index + 1
    ]

    start_event = segment_events[0]
    end_event = segment_events[-1]

    start_ts = parse_timestamp(start_event)
    end_ts = parse_timestamp(end_event)

    duration = 0.0

    if (
        start_ts is not None
        and end_ts is not None
    ):
        duration = (
            end_ts - start_ts
        ) / 1000.0

    return {
        "segment_id": (
            f"{session_id}_seg_{segment_number:04d}"
        ),
        "session_id": session_id,
        "start_ts": start_event.get(
            "timestamp_iso"
        ),
        "end_ts": end_event.get(
            "timestamp_iso"
        ),
        "start_event_index": start_index,
        "end_event_index": end_index,
        "event_count": len(segment_events),
        "duration_seconds": duration,
        "boundary_before": boundary_reason,
        "first_event_type": start_event.get(
            "event_type"
        ),
        "last_event_type": end_event.get(
            "event_type"
        ),
    }


# ============================================================
# SESSION SEGMENTATION
# ============================================================

def segment_session(
    session_id,
    events,
):
    if not events:
        return []

    events = sorted(
        events,
        key=lambda x: (
            parse_timestamp(x)
            if parse_timestamp(x) is not None
            else float("inf")
        ),
    )

    segments = []

    segment_start = 0
    segment_number = 1

    last_screenshot_ts = None
    boundary_reason = "session_start"

    for i, event in enumerate(events):

        event_type = get_event_type(event)

        if event_type in IGNORED_EVENTS:
            continue

        if event_type == "screenshot_smart":
            last_screenshot_ts = parse_timestamp(
                event
            )

        if i == segment_start:
            continue

        split, reason = should_split(
            events,
            i,
            segment_start,
            last_screenshot_ts,
        )

        if split:

            segment = create_segment(
                session_id=session_id,
                events=events,
                start_index=segment_start,
                end_index=i - 1,
                boundary_reason=reason,
                segment_number=segment_number,
            )

            segments.append(segment)

            segment_number += 1
            segment_start = i

            boundary_reason = reason

            # Recompute screenshot state for new segment.
            last_screenshot_ts = None

            for j in range(
                segment_start,
                i + 1,
            ):
                if (
                    events[j].get("event_type")
                    == "screenshot_smart"
                ):
                    last_screenshot_ts = parse_timestamp(
                        events[j]
                    )

    # Final segment.
    if segment_start < len(events):

        segment = create_segment(
            session_id=session_id,
            events=events,
            start_index=segment_start,
            end_index=len(events) - 1,
            boundary_reason=boundary_reason,
            segment_number=segment_number,
        )

        segments.append(segment)

    return segments


# ============================================================
# LOAD DATASET A
# ============================================================

def load_sessions():

    sessions = {}

    files = sorted(
        DATASET_A.rglob("events.jsonl")
    )

    for path in files:

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get(
                    "session_id"
                )

                if not session_id:
                    continue

                sessions.setdefault(
                    session_id,
                    []
                ).append(event)

    return sessions


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sessions = load_sessions()

    all_segments = []

    total_events = 0

    for session_id, events in sorted(
        sessions.items()
    ):

        total_events += len(events)

        segments = segment_session(
            session_id,
            events,
        )

        all_segments.extend(
            segments
        )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for segment in all_segments:

            f.write(
                json.dumps(
                    segment,
                    ensure_ascii=False,
                )
                + "\n"
            )

    durations = [
        x["duration_seconds"]
        for x in all_segments
    ]

    event_counts = [
        x["event_count"]
        for x in all_segments
    ]

    print("=" * 100)
    print("DATASET A — V8 SEGMENTATION")
    print("=" * 100)

    print(
        f"Sessions loaded       : "
        f"{len(sessions)}"
    )

    print(
        f"Events loaded         : "
        f"{total_events}"
    )

    print(
        f"Predicted segments    : "
        f"{len(all_segments)}"
    )

    if durations:

        sorted_durations = sorted(
            durations
        )

        median = sorted_durations[
            len(sorted_durations) // 2
        ]

        print(
            f"Min duration          : "
            f"{min(durations):.2f}s"
        )

        print(
            f"Median duration       : "
            f"{median:.2f}s"
        )

        print(
            f"Max duration          : "
            f"{max(durations):.2f}s"
        )

        print(
            f"Avg duration          : "
            f"{sum(durations) / len(durations):.2f}s"
        )

    if event_counts:

        print(
            f"Avg events/segment    : "
            f"{sum(event_counts) / len(event_counts):.2f}"
        )

    print("\nDURATION DISTRIBUTION")
    print("-" * 100)

    buckets = [
        ("<5s", lambda x: x < 5),
        ("5-15s", lambda x: 5 <= x < 15),
        ("15-30s", lambda x: 15 <= x < 30),
        ("30-60s", lambda x: 30 <= x < 60),
        (">=60s", lambda x: x >= 60),
    ]

    for name, condition in buckets:

        count = sum(
            condition(x)
            for x in durations
        )

        percentage = (
            count / len(durations) * 100
            if durations
            else 0
        )

        print(
            f"{name:8s}: "
            f"{count:5d} "
            f"({percentage:6.2f}%)"
        )

    print("\nBOUNDARY REASONS")
    print("-" * 100)

    boundary_counts = {}

    for segment in all_segments:

        reason = segment[
            "boundary_before"
        ]

        boundary_counts[reason] = (
            boundary_counts.get(reason, 0)
            + 1
        )

    for reason, count in sorted(
        boundary_counts.items(),
        key=lambda x: (-x[1], x[0]),
    ):

        print(
            f"{reason:35s}: "
            f"{count}"
        )

    print("\nOUTPUT")
    print("-" * 100)

    print(OUTPUT_FILE)

    print("=" * 100)


if __name__ == "__main__":
    main()