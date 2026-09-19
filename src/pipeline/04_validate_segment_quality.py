import json
import os
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEGMENTS_FILE = os.path.join(
    BASE_DIR,
    "outputs",
    "dataset_b_segments_v6.jsonl"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "outputs",
    "dataset_b_segment_quality.json"
)


# ------------------------------------------------------------
# Event types that indicate actual user interaction
# ------------------------------------------------------------

INTERACTION_TYPES = {
    "mouse_click",
    "browser_click",
    "keystroke",
    "shortcut",
    "clipboard_change",
    "browser_form_input",
    "mouse_scroll",
}


# ------------------------------------------------------------
# Load segments
# ------------------------------------------------------------

def load_segments():
    segments = []

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            segments.append(json.loads(line))

    return segments


# ------------------------------------------------------------
# Analyze one segment
# ------------------------------------------------------------

def analyze_segment(segment):

    event_type_counts = segment.get(
        "event_type_counts",
        {}
    )

    interaction_count = sum(
        count
        for event_type, count in event_type_counts.items()
        if event_type in INTERACTION_TYPES
    )

    total_events = segment.get(
        "event_count",
        0
    )

    completion_index = segment.get(
        "completion_event_index"
    )

    start_index = segment.get(
        "start_event_index"
    )

    end_index = segment.get(
        "end_event_index"
    )

    # Number of events from segment start through completion
    pre_completion_events = None

    if (
        completion_index is not None
        and start_index is not None
        and completion_index >= start_index
    ):
        pre_completion_events = (
            completion_index - start_index + 1
        )

    # How much post-completion context was included?
    post_completion_events = None

    if (
        completion_index is not None
        and end_index is not None
        and end_index >= completion_index
    ):
        post_completion_events = (
            end_index - completion_index
        )

    # Position of completion within segment.
    completion_position = None

    if (
        start_index is not None
        and end_index is not None
        and completion_index is not None
        and end_index >= start_index
    ):
        segment_length = (
            end_index - start_index + 1
        )

        completion_position = (
            completion_index - start_index + 1
        ) / segment_length

    return {
        "segment_id": segment.get("segment_id"),
        "task": segment.get("task"),
        "business_area": segment.get("business_area"),
        "duration_seconds": segment.get(
            "duration_seconds",
            0
        ),
        "event_count": total_events,
        "interaction_event_count": interaction_count,
        "pre_completion_event_count": pre_completion_events,
        "post_completion_event_count": post_completion_events,
        "completion_position": completion_position,
        "applications": segment.get(
            "applications",
            []
        ),
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    print("=" * 70)
    print("DATASET B SEGMENT QUALITY ANALYSIS")
    print("=" * 70)

    segments = load_segments()

    print(
        f"Segments loaded : {len(segments)}"
    )

    analyzed = [
        analyze_segment(segment)
        for segment in segments
    ]

    # --------------------------------------------------------
    # Interaction activity
    # --------------------------------------------------------

    with_interaction = [
        s
        for s in analyzed
        if s["interaction_event_count"] > 0
    ]

    no_interaction = [
        s
        for s in analyzed
        if s["interaction_event_count"] == 0
    ]

    # --------------------------------------------------------
    # Duration buckets
    # --------------------------------------------------------

    duration_buckets = Counter()

    for s in analyzed:

        duration = s["duration_seconds"]

        if duration < 1:
            bucket = "<1s"

        elif duration < 2:
            bucket = "1-2s"

        elif duration < 5:
            bucket = "2-5s"

        elif duration < 10:
            bucket = "5-10s"

        else:
            bucket = ">=10s"

        duration_buckets[bucket] += 1

    # --------------------------------------------------------
    # Completion position
    # --------------------------------------------------------

    completion_positions = [
        s["completion_position"]
        for s in analyzed
        if s["completion_position"] is not None
    ]

    near_end = [
        s
        for s in analyzed
        if (
            s["completion_position"] is not None
            and s["completion_position"] >= 0.8
        )
    ]

    # --------------------------------------------------------
    # Task-level summary
    # --------------------------------------------------------

    task_summary = {}

    for s in analyzed:

        task = s["task"]

        if task not in task_summary:
            task_summary[task] = {
                "segments": 0,
                "with_interaction": 0,
                "no_interaction": 0,
                "total_duration": 0.0,
                "total_interactions": 0,
            }

        item = task_summary[task]

        item["segments"] += 1
        item["total_duration"] += (
            s["duration_seconds"]
        )
        item["total_interactions"] += (
            s["interaction_event_count"]
        )

        if s["interaction_event_count"] > 0:
            item["with_interaction"] += 1
        else:
            item["no_interaction"] += 1

    # --------------------------------------------------------
    # Potentially weak segments
    # --------------------------------------------------------

    weak_segments = []

    for s in analyzed:

        reasons = []

        if s["interaction_event_count"] == 0:
            reasons.append(
                "no_interaction_events"
            )

        if (
            s["duration_seconds"] < 0.5
        ):
            reasons.append(
                "very_short_duration"
            )

        if (
            s["pre_completion_event_count"]
            is not None
            and s["pre_completion_event_count"] <= 1
        ):
            reasons.append(
                "little_activity_before_completion"
            )

        if reasons:

            weak_segments.append({
                "segment_id": s["segment_id"],
                "task": s["task"],
                "duration_seconds": s[
                    "duration_seconds"
                ],
                "event_count": s[
                    "event_count"
                ],
                "interaction_event_count": s[
                    "interaction_event_count"
                ],
                "pre_completion_event_count": s[
                    "pre_completion_event_count"
                ],
                "reasons": reasons,
            })

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print()
    print("INTERACTION ACTIVITY")
    print("-" * 70)

    print(
        f"Segments with interaction events : "
        f"{len(with_interaction)}"
    )

    print(
        f"Segments without interaction     : "
        f"{len(no_interaction)}"
    )

    print()
    print("DURATION DISTRIBUTION")
    print("-" * 70)

    bucket_order = [
        "<1s",
        "1-2s",
        "2-5s",
        "5-10s",
        ">=10s",
    ]

    for bucket in bucket_order:

        print(
            f"{bucket:<10}: "
            f"{duration_buckets[bucket]}"
        )

    print()
    print("COMPLETION POSITION")
    print("-" * 70)

    print(
        f"Segments with completion near end "
        f"(>=80%): {len(near_end)}"
    )

    if completion_positions:

        average_position = (
            sum(completion_positions)
            / len(completion_positions)
        )

        print(
            f"Average completion position: "
            f"{average_position:.2%}"
        )

    print()
    print("TASK QUALITY")
    print("-" * 70)

    for task in sorted(task_summary):

        item = task_summary[task]

        print(
            f"{task:<28} "
            f"{item['segments']:>3} segments | "
            f"{item['with_interaction']:>3} with interaction | "
            f"{item['no_interaction']:>3} without"
        )

    print()
    print("POTENTIALLY WEAK SEGMENTS")
    print("-" * 70)

    print(
        f"Potentially weak segments: "
        f"{len(weak_segments)}"
    )

    for item in weak_segments[:20]:

        print(
            f"{item['segment_id']} | "
            f"{item['task']} | "
            f"{item['duration_seconds']:.3f}s | "
            f"{', '.join(item['reasons'])}"
        )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    report = {
        "total_segments": len(analyzed),

        "interaction_activity": {
            "with_interaction": len(
                with_interaction
            ),
            "without_interaction": len(
                no_interaction
            ),
        },

        "duration_distribution": dict(
            duration_buckets
        ),

        "completion_position": {
            "segments_with_position": len(
                completion_positions
            ),
            "near_end_ge_80_percent": len(
                near_end
            ),
            "average_position": (
                sum(completion_positions)
                / len(completion_positions)
                if completion_positions
                else None
            ),
        },

        "task_summary": task_summary,

        "potentially_weak_segments": weak_segments,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 70)

    print(
        f"Quality report written to:\n"
        f"{OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()