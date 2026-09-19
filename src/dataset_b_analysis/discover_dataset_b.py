import os
import json
import csv
from collections import Counter
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATASET_B_DIR = os.path.join(
    BASE_DIR,
    "dataset_b"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "outputs"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def load_jsonl(path):

    records = []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError:
                continue

    return records


def get_event_type(event):

    return (
        event.get("event")
        or event.get("event_type")
        or event.get("type")
        or "unknown"
    )


def get_timestamp(event):

    value = (
        event.get("timestamp_ms")
        or event.get("timestamp")
        or event.get("ts")
        or event.get("time")
    )

    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Convert milliseconds to seconds
        if value > 1_000_000_000_000:
            return value / 1000.0

        return float(value)

    text = str(value).strip()

    # ISO timestamp
    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).timestamp()

    except ValueError:
        pass

    # Numeric timestamp
    try:
        number = float(text)

        if number > 1_000_000_000_000:
            return number / 1000.0

        return number

    except ValueError:
        return None

def get_app(event):

    app = event.get("active_app")

    if isinstance(app, dict):

        return str(
            app.get("app_name")
            or app.get("process_name")
            or "unknown"
        ).lower()

    if app:
        return str(app).lower()

    context = event.get("context")

    if isinstance(context, dict):

        app = (
            context.get("active_app")
            or context.get("application")
            or context.get("app")
        )

        if isinstance(app, dict):

            return str(
                app.get("app_name")
                or app.get("process_name")
                or "unknown"
            ).lower()

        if app:
            return str(app).lower()

    return "unknown"


def get_window_title(event):

    app = event.get("active_app")

    if isinstance(app, dict):

        title = app.get("window_title")

        if title:
            return str(title)

    context = event.get("context")

    if isinstance(context, dict):

        title = context.get("window_title")

        if title:
            return str(title)

        active_app = context.get("active_app")

        if isinstance(active_app, dict):

            title = active_app.get("window_title")

            if title:
                return str(title)

    return ""


def has_text(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return False

    text = context.get("extracted_text")

    return bool(
        text and str(text).strip()
    )


def get_text(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return ""

    text = context.get("extracted_text")

    if text:
        return str(text).strip()

    return ""


# ============================================================
# FIND DATASET B SESSIONS
# ============================================================

session_files = []

for root, dirs, files in os.walk(DATASET_B_DIR):

    for filename in files:

        if filename == "events.jsonl":

            session_files.append(
                os.path.join(root, filename)
            )

session_files.sort()


# ============================================================
# ANCHOR EVENTS
# ============================================================

ANCHOR_EVENTS = {
    "browser_navigation",
    "browser_form_input",
    "browser_click",
    "clipboard_change",
    "upload_started",
    "upload_completed",
    "window_title_change",
    "text_input_complete",
}


# ============================================================
# GAP THRESHOLDS
# ============================================================

# We intentionally use a fairly conservative threshold.
#
# A short pause does NOT mean a new business process.
#
# We first identify candidate boundaries and inspect them.

GAP_THRESHOLD_SECONDS = 60


# ============================================================
# OUTPUT CONTAINERS
# ============================================================

candidate_segments = []

gap_rows = []

session_profiles = []


# ============================================================
# PROCESS EACH SESSION
# ============================================================

global_segment_id = 0


for session_path in session_files:

    session_id = os.path.basename(
        os.path.dirname(session_path)
    )

    events = load_jsonl(session_path)

    # --------------------------------------------------------
    # Sort by timestamp when timestamps are available
    # --------------------------------------------------------

    indexed_events = []

    for index, event in enumerate(events):

        ts = get_timestamp(event)

        indexed_events.append(
            (
                ts if ts is not None else float(index),
                index,
                event
            )
        )

    indexed_events.sort(
        key=lambda x: x[0]
    )

    events = [
        item[2]
        for item in indexed_events
    ]

    # --------------------------------------------------------
    # Session-level counters
    # --------------------------------------------------------

    event_counter = Counter()
    app_counter = Counter()
    anchor_counter = Counter()

    gaps = []

    # --------------------------------------------------------
    # Calculate gaps
    # --------------------------------------------------------

    previous_ts = None

    for index, event in enumerate(events):

        ts = get_timestamp(event)

        event_type = get_event_type(event)
        app = get_app(event)

        event_counter[event_type] += 1
        app_counter[app] += 1

        if event_type in ANCHOR_EVENTS:
            anchor_counter[event_type] += 1

        if ts is not None and previous_ts is not None:

            gap = ts - previous_ts

            if gap >= 0:

                gaps.append(gap)

                if gap >= GAP_THRESHOLD_SECONDS:

                    gap_rows.append(
                        {
                            "session_id": session_id,
                            "event_index": index,
                            "gap_seconds": round(
                                gap,
                                2
                            ),
                            "previous_event": get_event_type(
                                events[index - 1]
                            ),
                            "next_event": event_type,
                            "previous_app": get_app(
                                events[index - 1]
                            ),
                            "next_app": app,
                            "next_window": get_window_title(
                                event
                            ),
                        }
                    )

        if ts is not None:
            previous_ts = ts

    # --------------------------------------------------------
    # Candidate segmentation
    # --------------------------------------------------------

    start_index = 0

    segment_number = 0

    for index in range(1, len(events)):

        previous_ts = get_timestamp(
            events[index - 1]
        )

        current_ts = get_timestamp(
            events[index]
        )

        if (
            previous_ts is None
            or current_ts is None
        ):
            continue

        gap = current_ts - previous_ts

        if gap >= GAP_THRESHOLD_SECONDS:

            segment_events = events[
                start_index:index
            ]

            if segment_events:

                segment_number += 1
                global_segment_id += 1

                segment_event_types = Counter(
                    get_event_type(e)
                    for e in segment_events
                )

                segment_apps = Counter(
                    get_app(e)
                    for e in segment_events
                )

                segment_text = [
                    get_text(e)
                    for e in segment_events
                    if has_text(e)
                ]

                first_ts = get_timestamp(
                    segment_events[0]
                )

                last_ts = get_timestamp(
                    segment_events[-1]
                )

                duration = None

                if (
                    first_ts is not None
                    and last_ts is not None
                ):

                    duration = (
                        last_ts - first_ts
                    )

                candidate_segments.append(
                    {
                        "segment_id":
                            f"BSEG_{global_segment_id:04d}",

                        "session_id":
                            session_id,

                        "segment_number":
                            segment_number,

                        "start_index":
                            start_index,

                        "end_index":
                            index - 1,

                        "event_count":
                            len(segment_events),

                        "duration_seconds":
                            duration,

                        "event_types":
                            dict(
                                segment_event_types
                            ),

                        "applications":
                            dict(
                                segment_apps
                            ),

                        "text_evidence":
                            segment_text[:10],

                        "first_window":
                            get_window_title(
                                segment_events[0]
                            ),

                        "last_window":
                            get_window_title(
                                segment_events[-1]
                            ),
                    }
                )

            start_index = index

    # --------------------------------------------------------
    # Last segment
    # --------------------------------------------------------

    if start_index < len(events):

        segment_events = events[
            start_index:
        ]

        segment_number += 1
        global_segment_id += 1

        segment_event_types = Counter(
            get_event_type(e)
            for e in segment_events
        )

        segment_apps = Counter(
            get_app(e)
            for e in segment_events
        )

        segment_text = [
            get_text(e)
            for e in segment_events
            if has_text(e)
        ]

        first_ts = get_timestamp(
            segment_events[0]
        )

        last_ts = get_timestamp(
            segment_events[-1]
        )

        duration = None

        if (
            first_ts is not None
            and last_ts is not None
        ):

            duration = (
                last_ts - first_ts
            )

        candidate_segments.append(
            {
                "segment_id":
                    f"BSEG_{global_segment_id:04d}",

                "session_id":
                    session_id,

                "segment_number":
                    segment_number,

                "start_index":
                    start_index,

                "end_index":
                    len(events) - 1,

                "event_count":
                    len(segment_events),

                "duration_seconds":
                    duration,

                "event_types":
                    dict(
                        segment_event_types
                    ),

                "applications":
                    dict(
                        segment_apps
                    ),

                "text_evidence":
                    segment_text[:10],

                "first_window":
                    get_window_title(
                        segment_events[0]
                    ),

                "last_window":
                    get_window_title(
                        segment_events[-1]
                    ),
            }
        )


    # --------------------------------------------------------
    # Session profile
    # --------------------------------------------------------

    session_profiles.append(
        {
            "session_id": session_id,
            "events": len(events),
            "unique_apps": len(app_counter),
            "anchors": sum(
                anchor_counter.values()
            ),
            "gaps_over_60s": sum(
                1
                for gap in gaps
                if gap >= GAP_THRESHOLD_SECONDS
            ),
            "max_gap_seconds": (
                round(max(gaps), 2)
                if gaps
                else 0
            ),
        }
    )


# ============================================================
# PRINT COMPACT RESULTS
# ============================================================

print()
print("=" * 70)
print("DATASET B CANDIDATE SEGMENT DISCOVERY")
print("=" * 70)

print()
print(f"Sessions              : {len(session_files)}")
print(f"Candidate segments    : {len(candidate_segments)}")
print(f"Gap threshold         : {GAP_THRESHOLD_SECONDS}s")
print(
    f"Gaps >= threshold     : {len(gap_rows)}"
)


# ============================================================
# SESSION PROFILES
# ============================================================

print()
print("=" * 70)
print("SESSION GAP PROFILE")
print("=" * 70)

for row in sorted(
    session_profiles,
    key=lambda x: x["events"],
    reverse=True
):

    print(
        f"{row['session_id']:32s}"
        f" events={row['events']:5d}"
        f" gaps={row['gaps_over_60s']:3d}"
        f" max_gap={row['max_gap_seconds']:8.1f}s"
    )


# ============================================================
# LARGEST GAPS
# ============================================================

print()
print("=" * 70)
print("LARGEST ACTIVITY GAPS")
print("=" * 70)

for row in sorted(
    gap_rows,
    key=lambda x: x["gap_seconds"],
    reverse=True
)[:30]:

    print(
        f"{row['session_id']:32s}"
        f" {row['gap_seconds']:8.1f}s"
        f" {row['previous_app']:20s}"
        f" -> {row['next_app']:20s}"
    )


# ============================================================
# CANDIDATE SEGMENT SUMMARY
# ============================================================

print()
print("=" * 70)
print("CANDIDATE SEGMENTS")
print("=" * 70)

for segment in candidate_segments:

    apps = ", ".join(
        sorted(
            segment["applications"].keys()
        )
    )

    print(
        f"{segment['segment_id']:10s}"
        f" {segment['session_id']:32s}"
        f" events={segment['event_count']:4d}"
        f" duration="
        f"{segment['duration_seconds'] or 0:7.1f}s"
        f" apps=[{apps}]"
    )


# ============================================================
# SAVE CANDIDATE SEGMENTS
# ============================================================

segments_path = os.path.join(
    OUTPUT_DIR,
    "dataset_b_candidate_segments.jsonl"
)

with open(
    segments_path,
    "w",
    encoding="utf-8"
) as f:

    for segment in candidate_segments:

        f.write(
            json.dumps(
                segment,
                ensure_ascii=False
            )
            + "\n"
        )


# ============================================================
# SAVE GAP REPORT
# ============================================================

gaps_path = os.path.join(
    OUTPUT_DIR,
    "dataset_b_activity_gaps.csv"
)

with open(
    gaps_path,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "session_id",
            "event_index",
            "gap_seconds",
            "previous_event",
            "next_event",
            "previous_app",
            "next_app",
            "next_window",
        ]
    )

    writer.writeheader()

    writer.writerows(gap_rows)


# ============================================================
# SAVE SESSION PROFILE
# ============================================================

profile_path = os.path.join(
    OUTPUT_DIR,
    "dataset_b_session_gap_profile.csv"
)

with open(
    profile_path,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "session_id",
            "events",
            "unique_apps",
            "anchors",
            "gaps_over_60s",
            "max_gap_seconds",
        ]
    )

    writer.writeheader()

    writer.writerows(session_profiles)


# ============================================================
# DONE
# ============================================================

print()
print("=" * 70)
print("OUTPUT FILES")
print("=" * 70)

print(f"Candidate segments : {segments_path}")
print(f"Activity gaps      : {gaps_path}")
print(f"Session profiles    : {profile_path}")

print()
print("Candidate discovery complete.")