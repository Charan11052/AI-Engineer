import json
import importlib.util
from pathlib import Path
from collections import Counter


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET_B = ROOT / "data" / "dataset_b"
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

OUTPUT_FILE = (
    OUTPUT_DIR / "dataset_b_segments_v7.jsonl"
)

V6_FILE = (
    ROOT
    / "src"
    / "pipeline"
    / "01_segment_dataset_b.py"
)


# ============================================================
# START DETECTION CONFIGURATION
# ============================================================

# Evidence from Dataset B shows >=5s gaps are much more common
# than >=8s gaps and therefore provide a useful boundary signal.
STRONG_GAP_SECONDS = 5.0

# Very long gaps are treated as extremely strong boundaries.
VERY_STRONG_GAP_SECONDS = 8.0

# Maximum amount of history inspected for a completion.
MAX_LOOKBACK_SECONDS = 60.0

# Do not allow a segment to become arbitrarily long.
MAX_SEGMENT_SECONDS = 120.0

# Context after completion.
POST_COMPLETION_SECONDS = 2.0

# Minimum number of meaningful events for a non-trivial segment.
MIN_ACTIVITY_EVENTS = 2


# ============================================================
# ACTIVITY TYPES
# ============================================================

ACTIVITY_TYPES = {
    "mouse_click",
    "browser_click",
    "browser_navigation",
    "browser_form_input",
    "keystroke",
    "shortcut",
    "clipboard_change",
    "mouse_scroll",
    "app_switch",
}


# High-value task-start signals.
STRONG_START_TYPES = {
    "browser_navigation",
    "browser_form_input",
}

MEDIUM_START_TYPES = {
    "mouse_click",
    "browser_click",
    "shortcut",
    "app_switch",
}

WEAK_START_TYPES = {
    "keystroke",
    "mouse_scroll",
    "clipboard_change",
}


# ============================================================
# LOAD V6 MODULE
# ============================================================

def load_v6_module():

    spec = importlib.util.spec_from_file_location(
        "dataset_b_v6",
        V6_FILE,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Could not load V6 pipeline: {V6_FILE}"
        )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


V6 = load_v6_module()


# ============================================================
# V6 COMPATIBILITY HELPERS
# ============================================================

def get_event_text(event):
    return V6.get_event_text(event)


def get_active_app(event):
    return V6.get_active_app(event)


def detect_completion(event):
    return V6.detect_completion(event)


def detect_supporting_tasks(event):
    return V6.detect_supporting_tasks(event)


# ============================================================
# EVENT HELPERS
# ============================================================

def event_type(event):
    return str(
        event.get(
            "event_type",
            "unknown",
        )
    )


def is_activity(event):
    return event_type(event) in ACTIVITY_TYPES


def parse_timestamp(event):

    value = event.get("timestamp_ms")

    if value is not None:

        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    return V6.parse_timestamp(event)


def get_window_identity(event):

    context = event.get(
        "context",
        {},
    )

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        app = (
            active_app.get("app_name")
            or active_app.get("process_name")
            or "unknown"
        )

        title = (
            active_app.get("window_title")
            or ""
        )

    else:

        app = "unknown"
        title = ""

    return (
        str(app).lower(),
        str(title).lower(),
    )


# ============================================================
# TASK EVIDENCE
# ============================================================

def task_evidence(event, task):

    tasks = detect_supporting_tasks(
        event
    )

    return task in tasks


def competing_task_evidence(
    event,
    task,
):

    tasks = detect_supporting_tasks(
        event
    )

    return [
        candidate
        for candidate in tasks
        if candidate != task
    ]


# ============================================================
# LOAD DATASET
# ============================================================

def load_chunks():

    chunks = []

    paths = sorted(
        DATASET_B.rglob("events.jsonl")
    )

    print(
        f"Dataset B root: {DATASET_B}"
    )

    print(
        f"Found chunks: {len(paths)}"
    )

    for path in paths:

        events = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = parse_timestamp(
                    event
                )

                if timestamp is None:
                    continue

                event["_ts"] = timestamp

                events.append(event)

        if not events:
            continue

        events.sort(
            key=lambda x: x["_ts"]
        )

        chunks.append(
            {
                "path": path,
                "session":
                    path.parent.parent.name,
                "chunk":
                    path.parent.name,
                "events":
                    events,
            }
        )

    return chunks


# ============================================================
# CONTEXT CHANGE
# ============================================================

def context_changed(
    previous,
    current,
):

    return (
        get_window_identity(
            previous
        )
        !=
        get_window_identity(
            current
        )
    )


def app_changed(
    previous,
    current,
):

    previous_id = (
        get_window_identity(
            previous
        )
    )

    current_id = (
        get_window_identity(
            current
        )
    )

    return previous_id[0] != current_id[0]


def window_changed(
    previous,
    current,
):

    previous_id = (
        get_window_identity(
            previous
        )
    )

    current_id = (
        get_window_identity(
            current
        )
    )

    return previous_id[1] != current_id[1]


# ============================================================
# BUILD BACKWARD WINDOW
# ============================================================

def get_lookback(
    events,
    completion_index,
):

    completion_ts = (
        events[
            completion_index
        ]["_ts"]
    )

    minimum_ts = (
        completion_ts
        - MAX_LOOKBACK_SECONDS * 1000
    )

    result = []

    for index in range(
        completion_index,
        -1,
        -1,
    ):

        event = events[index]

        if event["_ts"] < minimum_ts:
            break

        result.append(
            (
                index,
                event,
            )
        )

    result.reverse()

    return result


# ============================================================
# FIND BOUNDARY CANDIDATES
# ============================================================

def collect_boundaries(
    window,
    task,
):

    candidates = []

    for i in range(
        1,
        len(window),
    ):

        previous_index, previous = (
            window[i - 1]
        )

        current_index, current = (
            window[i]
        )

        gap = (
            current["_ts"]
            - previous["_ts"]
        ) / 1000.0

        current_type = event_type(
            current
        )

        current_task_evidence = (
            task_evidence(
                current,
                task,
            )
        )

        competing = (
            competing_task_evidence(
                current,
                task,
            )
        )

        score = 0.0
        reasons = []

        # ----------------------------------------------------
        # Idle gap
        # ----------------------------------------------------

        if gap >= VERY_STRONG_GAP_SECONDS:

            score += 7.0

            reasons.append(
                "idle_gap_>=8s"
            )

        elif gap >= STRONG_GAP_SECONDS:

            score += 5.0

            reasons.append(
                "idle_gap_>=5s"
            )

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------

        if current_type == (
            "browser_navigation"
        ):

            score += 5.0

            reasons.append(
                "browser_navigation"
            )

        # ----------------------------------------------------
        # Form input
        # ----------------------------------------------------

        elif current_type == (
            "browser_form_input"
        ):

            score += 4.0

            reasons.append(
                "browser_form_input"
            )

        # ----------------------------------------------------
        # Click
        # ----------------------------------------------------

        elif current_type in {
            "mouse_click",
            "browser_click",
        }:

            score += 2.0

            reasons.append(
                "click"
            )

        # ----------------------------------------------------
        # Shortcut
        # ----------------------------------------------------

        elif current_type == "shortcut":

            score += 2.0

            reasons.append(
                "shortcut"
            )

        # ----------------------------------------------------
        # App / window change
        # ----------------------------------------------------

        if app_changed(
            previous,
            current,
        ):

            score += 3.0

            reasons.append(
                "app_change"
            )

        elif window_changed(
            previous,
            current,
        ):

            score += 2.0

            reasons.append(
                "window_change"
            )

        # ----------------------------------------------------
        # Task-specific evidence
        # ----------------------------------------------------

        if current_task_evidence:

            score += 3.0

            reasons.append(
                "task_evidence"
            )

        # ----------------------------------------------------
        # Competing task evidence
        # ----------------------------------------------------

        if competing:

            score -= 3.0

            reasons.append(
                "competing_task_evidence"
            )

        # ----------------------------------------------------
        # Only meaningful candidates
        # ----------------------------------------------------

        if score <= 0:
            continue

        candidates.append(
            {
                "index":
                    current_index,

                "timestamp_ms":
                    current["_ts"],

                "event_type":
                    current_type,

                "score":
                    score,

                "reasons":
                    reasons,

                "gap_seconds":
                    gap,

                "task_evidence":
                    current_task_evidence,

                "competing_tasks":
                    competing,

                "app":
                    get_active_app(
                        current
                    ),

                "text":
                    get_event_text(
                        current
                    ),
            }
        )

    return candidates


# ============================================================
# FIND START
# ============================================================

def find_start(
    events,
    completion_index,
    task,
    minimum_index,
):

    window = get_lookback(
        events,
        completion_index,
    )

    # Respect already-used events.
    window = [
        (
            index,
            event,
        )
        for index, event in window
        if index >= minimum_index
    ]

    if not window:
        return {
            "start_index":
                completion_index,

            "method":
                "completion_fallback",

            "score":
                0.0,

            "reasons":
                [],
        }

    candidates = collect_boundaries(
        window,
        task,
    )

    if not candidates:

        # Conservative fallback:
        # use the first meaningful activity in
        # the available window rather than claiming
        # the entire 60 seconds is definitely one task.
        for index, event in window:

            if is_activity(event):

                return {
                    "start_index":
                        index,

                    "method":
                        "first_activity_fallback",

                    "score":
                        0.0,

                    "reasons":
                        [
                            "no_strong_boundary"
                        ],
                }

        return {
            "start_index":
                completion_index,

            "method":
                "completion_fallback",

            "score":
                0.0,

            "reasons":
                [],
        }

    # --------------------------------------------------------
    # We want the most recent strong boundary that still has
    # meaningful task activity after it.
    #
    # First identify candidates with strong evidence.
    # --------------------------------------------------------

    strong_candidates = [
        candidate
        for candidate in candidates
        if candidate["score"] >= 5.0
    ]

    if strong_candidates:

        selected = strong_candidates[-1]

        return {
            "start_index":
                selected["index"],

            "method":
                "strong_boundary",

            "score":
                selected["score"],

            "reasons":
                selected["reasons"],
        }

    # --------------------------------------------------------
    # Otherwise use the highest-scoring recent candidate.
    # --------------------------------------------------------

    selected = max(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["timestamp_ms"],
        ),
    )

    return {
        "start_index":
            selected["index"],

        "method":
            "scored_boundary",

        "score":
            selected["score"],

        "reasons":
            selected["reasons"],
    }


# ============================================================
# FIND END
# ============================================================

def find_end(
    events,
    completion_index,
):

    completion_ts = (
        events[
            completion_index
        ]["_ts"]
    )

    end_index = completion_index

    for i in range(
        completion_index + 1,
        len(events),
    ):

        current_ts = (
            events[i]["_ts"]
        )

        if (
            current_ts
            - completion_ts
            > POST_COMPLETION_SECONDS
            * 1000
        ):
            break

        end_index = i

    return end_index


# ============================================================
# BUILD SEGMENT
# ============================================================

def build_segment(
    events,
    start_index,
    end_index,
    completion_index,
    task,
    session,
    chunk,
    number,
    start_info,
):

    segment_events = events[
        start_index:
        end_index + 1
    ]

    start_ts = (
        segment_events[0]["_ts"]
    )

    end_ts = (
        segment_events[-1]["_ts"]
    )

    applications = []
    event_counts = Counter()

    supporting_tasks = set()

    for event in segment_events:

        app = get_active_app(
            event
        )

        if app not in applications:
            applications.append(app)

        event_counts[
            event_type(event)
        ] += 1

        for supporting in (
            detect_supporting_tasks(
                event
            )
        ):

            supporting_tasks.add(
                supporting
            )

    completion_text = (
        get_event_text(
            events[
                completion_index
            ]
        )
    )

    activity_count = sum(
        1
        for event in segment_events
        if is_activity(event)
    )

    duration = (
        end_ts - start_ts
    ) / 1000.0

    return {
        "segment_id":
            (
                f"{session}__"
                f"{chunk}__"
                f"segment_{number:04d}"
            ),

        "session":
            session,

        "chunk":
            chunk,

        "task":
            task,

        "business_area":
            V6.TASK_TO_AREA.get(
                task,
                "Other",
            ),

        "start_timestamp_ms":
            start_ts,

        "end_timestamp_ms":
            end_ts,

        "duration_seconds":
            round(
                duration,
                3,
            ),

        "event_count":
            len(segment_events),

        "activity_event_count":
            activity_count,

        "applications":
            applications,

        "supporting_tasks":
            sorted(
                supporting_tasks
            ),

        "completion_evidence":
            completion_text,

        "completion_event_index":
            completion_index,

        "start_event_index":
            start_index,

        "end_event_index":
            end_index,

        "start_detection":
            {
                "method":
                    start_info[
                        "method"
                    ],

                "score":
                    start_info[
                        "score"
                    ],

                "reasons":
                    start_info[
                        "reasons"
                    ],
            },

        "event_type_counts":
            dict(event_counts),

        "confidence":
            (
                "high"
                if start_info[
                    "score"
                ] >= 5
                else "medium"
            ),
    }


# ============================================================
# SEGMENT CHUNK
# ============================================================

def segment_chunk(chunk):

    events = chunk["events"]

    session = chunk["session"]
    chunk_name = chunk["chunk"]

    segments = []

    used_until = -1

    segment_number = 1

    for i, event in enumerate(events):

        task = detect_completion(
            event
        )

        if task is None:
            continue

        if i <= used_until:
            continue

        start_info = find_start(
            events,
            i,
            task,
            used_until + 1,
        )

        start_index = (
            start_info[
                "start_index"
            ]
        )

        end_index = find_end(
            events,
            i,
        )

        if start_index <= used_until:
            continue

        # ----------------------------------------------------
        # Sanity checks
        # ----------------------------------------------------

        duration = (
            events[end_index]["_ts"]
            - events[start_index]["_ts"]
        ) / 1000.0

        if duration > MAX_SEGMENT_SECONDS:

            # If the chosen start creates an excessively long
            # segment, fall back to the latest strong boundary.
            window = get_lookback(
                events,
                i,
            )

            strong = [
                candidate
                for candidate
                in collect_boundaries(
                    window,
                    task,
                )
                if candidate["score"] >= 5
            ]

            if strong:

                latest = strong[-1]

                start_index = (
                    latest["index"]
                )

                start_info = {
                    "start_index":
                        start_index,

                    "method":
                        "duration_guard",

                    "score":
                        latest["score"],

                    "reasons":
                        latest["reasons"],
                }

        activity_count = sum(
            1
            for event in events[
                start_index:
                end_index + 1
            ]
            if is_activity(event)
        )

        if activity_count < MIN_ACTIVITY_EVENTS:
            continue

        segment = build_segment(
            events=events,
            start_index=start_index,
            end_index=end_index,
            completion_index=i,
            task=task,
            session=session,
            chunk=chunk_name,
            number=segment_number,
            start_info=start_info,
        )

        segments.append(
            segment
        )

        used_until = end_index
        segment_number += 1

    return segments


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print(
        "DATASET B — START-AWARE SEGMENTATION V7"
    )
    print("=" * 70)

    print(
        f"Dataset B: {DATASET_B}"
    )

    chunks = load_chunks()

    print(
        f"Chunks loaded: {len(chunks)}"
    )

    total_events = sum(
        len(chunk["events"])
        for chunk in chunks
    )

    print(
        f"Events loaded: {total_events}"
    )

    all_segments = []

    for chunk in chunks:

        segments = segment_chunk(
            chunk
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

    print()
    print(
        f"Segments: {len(all_segments)}"
    )

    if not all_segments:

        print(
            "WARNING: No segments detected."
        )

        return

    durations = [
        segment[
            "duration_seconds"
        ]
        for segment in all_segments
    ]

    activity_counts = [
        segment[
            "activity_event_count"
        ]
        for segment in all_segments
    ]

    task_counts = Counter(
        segment["task"]
        for segment in all_segments
    )

    method_counts = Counter(
        segment[
            "start_detection"
        ]["method"]
        for segment in all_segments
    )

    confidence_counts = Counter(
        segment["confidence"]
        for segment in all_segments
    )

    print()
    print("Duration:")
    print(
        f"  avg: {sum(durations) / len(durations):.2f}s"
    )
    print(
        f"  min: {min(durations):.2f}s"
    )
    print(
        f"  max: {max(durations):.2f}s"
    )

    print()
    print("Activity events:")
    print(
        f"  avg: "
        f"{sum(activity_counts) / len(activity_counts):.1f}"
    )

    print()
    print("Tasks:")

    for task, count in (
        task_counts.most_common()
    ):

        print(
            f"  {task}: {count}"
        )

    print()
    print("Start detection methods:")

    for method, count in (
        method_counts.most_common()
    ):

        print(
            f"  {method}: {count}"
        )

    print()
    print("Confidence:")

    for confidence, count in (
        confidence_counts.most_common()
    ):

        print(
            f"  {confidence}: {count}"
        )

    print()
    print(
        f"Output written to: {OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()