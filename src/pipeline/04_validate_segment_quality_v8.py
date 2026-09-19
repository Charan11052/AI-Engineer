from pathlib import Path
import json
import statistics
from collections import Counter


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET_B = ROOT / "data" / "dataset_b"
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

SEGMENTS_FILE = OUTPUT_DIR / "dataset_b_segments_v8.jsonl"


# ============================================================
# LOAD SEGMENTS
# ============================================================

def load_segments():
    segments = []

    if not SEGMENTS_FILE.exists():
        raise FileNotFoundError(
            f"V8 segments not found:\n{SEGMENTS_FILE}"
        )

    with SEGMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            segments.append(json.loads(line))

    return segments


# ============================================================
# FIELD HELPERS
# ============================================================

def get_duration(segment):
    if segment.get("duration_seconds") is not None:
        return float(segment["duration_seconds"])

    start = (
        segment.get("start_timestamp_ms")
        or segment.get("start_ts_ms")
        or segment.get("start_time_ms")
    )

    end = (
        segment.get("end_timestamp_ms")
        or segment.get("end_ts_ms")
        or segment.get("end_time_ms")
    )

    if start is not None and end is not None:
        return (float(end) - float(start)) / 1000.0

    return 0.0


def get_activity_count(segment):
    for key in (
        "activity_event_count",
        "activity_events",
        "num_activity_events",
    ):
        if segment.get(key) is not None:
            return int(segment[key])

    for key in (
        "event_count",
        "num_events",
    ):
        if segment.get(key) is not None:
            return int(segment[key])

    return 0


def get_task(segment):
    return (
        segment.get("task")
        or segment.get("task_type")
        or segment.get("task_name")
        or "UNKNOWN"
    )


def get_area(segment):
    return (
        segment.get("business_area")
        or segment.get("businessArea")
        or "UNKNOWN"
    )


def get_confidence(segment):
    return segment.get(
        "start_confidence",
        "unknown"
    )


def get_method(segment):
    return segment.get(
        "start_detection_method",
        "unknown"
    )


def get_completion_position(segment):
    """
    Returns completion position as a fraction of the segment.

    1.0 means completion is at the very end.
    0.5 means completion is halfway through.
    """

    start = (
        segment.get("start_timestamp_ms")
        or segment.get("start_ts_ms")
        or segment.get("start_time_ms")
    )

    end = (
        segment.get("end_timestamp_ms")
        or segment.get("end_ts_ms")
        or segment.get("end_time_ms")
    )

    completion = (
        segment.get("completion_timestamp_ms")
        or segment.get("completion_ts_ms")
        or segment.get("completion_time_ms")
    )

    if start is None or end is None or completion is None:
        return None

    duration = float(end) - float(start)

    if duration <= 0:
        return None

    position = (
        float(completion) - float(start)
    ) / duration

    return max(0.0, min(1.0, position))


# ============================================================
# DURATION BUCKETS
# ============================================================

def duration_buckets(durations):

    buckets = [
        ("<1s", lambda x: x < 1),
        ("1-2s", lambda x: 1 <= x < 2),
        ("2-5s", lambda x: 2 <= x < 5),
        ("5-10s", lambda x: 5 <= x < 10),
        ("10-30s", lambda x: 10 <= x < 30),
        ("30-60s", lambda x: 30 <= x < 60),
        ("60-120s", lambda x: 60 <= x <= 120),
        (">120s", lambda x: x > 120),
    ]

    for name, rule in buckets:
        count = sum(rule(x) for x in durations)
        print(f"{name:<10}: {count}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET B V8 — SEGMENT QUALITY ANALYSIS")
    print("=" * 70)

    segments = load_segments()

    print()
    print(f"V8 segments loaded : {len(segments)}")

    if not segments:
        print("ERROR: No V8 segments found.")
        return

    # --------------------------------------------------------
    # BASIC STATISTICS
    # --------------------------------------------------------

    durations = [
        get_duration(s)
        for s in segments
    ]

    activity_counts = [
        get_activity_count(s)
        for s in segments
    ]

    print()
    print("=" * 70)
    print("DURATION")
    print("=" * 70)

    print(f"Average : {statistics.mean(durations):.2f}s")
    print(f"Median  : {statistics.median(durations):.2f}s")
    print(f"Minimum : {min(durations):.2f}s")
    print(f"Maximum : {max(durations):.2f}s")

    print()
    print("Duration buckets:")
    duration_buckets(durations)

    # --------------------------------------------------------
    # ACTIVITY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("ACTIVITY EVENTS")
    print("=" * 70)

    valid_activity = [
        x for x in activity_counts
        if x >= 0
    ]

    if valid_activity:
        print(
            f"Average activity events : "
            f"{statistics.mean(valid_activity):.2f}"
        )

        print(
            f"Median activity events  : "
            f"{statistics.median(valid_activity):.2f}"
        )

        print(
            f"Minimum activity events : "
            f"{min(valid_activity)}"
        )

        print(
            f"Maximum activity events : "
            f"{max(valid_activity)}"
        )

    # --------------------------------------------------------
    # BUSINESS AREAS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BUSINESS AREAS")
    print("=" * 70)

    areas = Counter(
        get_area(s)
        for s in segments
    )

    for area, count in areas.most_common():
        print(
            f"{area:<25} {count}"
        )

    # --------------------------------------------------------
    # TASKS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TASK DISTRIBUTION")
    print("=" * 70)

    tasks = Counter(
        get_task(s)
        for s in segments
    )

    for task, count in tasks.most_common():
        print(
            f"{task:<30} {count}"
        )

    # --------------------------------------------------------
    # START DETECTION
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("START DETECTION METHODS")
    print("=" * 70)

    methods = Counter(
        get_method(s)
        for s in segments
    )

    for method, count in methods.most_common():
        print(
            f"{method:<35} {count}"
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("START CONFIDENCE")
    print("=" * 70)

    confidence = Counter(
        get_confidence(s)
        for s in segments
    )

    for level, count in confidence.most_common():
        print(
            f"{level:<15} {count}"
        )

    # --------------------------------------------------------
    # COMPLETION POSITION
    # --------------------------------------------------------

    positions = [
        get_completion_position(s)
        for s in segments
    ]

    positions = [
        x for x in positions
        if x is not None
    ]

    print()
    print("=" * 70)
    print("COMPLETION POSITION")
    print("=" * 70)

    if positions:

        print(
            f"Average completion position : "
            f"{statistics.mean(positions):.3f}"
        )

        print(
            f"Median completion position  : "
            f"{statistics.median(positions):.3f}"
        )

        for threshold in [0.5, 0.7, 0.8, 0.9]:

            count = sum(
                x >= threshold
                for x in positions
            )

            print(
                f"Completion >= {threshold:.1f} "
                f": {count} / {len(positions)} "
                f"({100 * count / len(positions):.2f}%)"
            )

    else:
        print(
            "Completion-position fields "
            "were not available."
        )

    # --------------------------------------------------------
    # QUALITY FLAGS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("QUALITY FLAGS")
    print("=" * 70)

    zero_or_negative = sum(
        x <= 0
        for x in durations
    )

    under_5 = sum(
        x < 5
        for x in durations
    )

    under_10 = sum(
        x < 10
        for x in durations
    )

    over_120 = sum(
        x > 120
        for x in durations
    )

    low_confidence = sum(
        get_confidence(s) == "low"
        for s in segments
    )

    print(
        f"Zero/negative duration : "
        f"{zero_or_negative}"
    )

    print(
        f"<5s segments           : "
        f"{under_5}"
    )

    print(
        f"<10s segments          : "
        f"{under_10}"
    )

    print(
        f">120s segments         : "
        f"{over_120}"
    )

    print(
        f"Low-confidence starts  : "
        f"{low_confidence}"
    )

    # --------------------------------------------------------
    # SHORTEST SEGMENTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("10 SHORTEST SEGMENTS")
    print("=" * 70)

    for segment in sorted(
        segments,
        key=get_duration
    )[:10]:

        print(
            f"{get_duration(segment):6.2f}s | "
            f"{get_task(segment):25} | "
            f"{get_method(segment):25} | "
            f"{get_confidence(segment)}"
        )

    # --------------------------------------------------------
    # LONGEST SEGMENTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("10 LONGEST SEGMENTS")
    print("=" * 70)

    for segment in sorted(
        segments,
        key=get_duration,
        reverse=True
    )[:10]:

        print(
            f"{get_duration(segment):6.2f}s | "
            f"{get_task(segment):25} | "
            f"{get_method(segment):25} | "
            f"{get_confidence(segment)}"
        )

    # --------------------------------------------------------
    # FINAL ASSESSMENT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("V8 QUALITY SUMMARY")
    print("=" * 70)

    print(
        f"Segments                 : {len(segments)}"
    )

    print(
        f"Average duration         : "
        f"{statistics.mean(durations):.2f}s"
    )

    print(
        f"Median duration          : "
        f"{statistics.median(durations):.2f}s"
    )

    print(
        f"<5s segments             : {under_5}"
    )

    print(
        f">120s segments           : {over_120}"
    )

    print(
        f"Low-confidence starts    : "
        f"{low_confidence}"
    )

    print()
    print("QUALITY ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()