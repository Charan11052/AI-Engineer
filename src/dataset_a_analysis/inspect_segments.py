import json
import os
from collections import Counter


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

SEGMENTS_FILE = os.path.join(
    BASE_DIR,
    "outputs",
    "segments.jsonl"
)


def main():

    print("=" * 80)
    print("DATASET B SEGMENT INSPECTION")
    print("=" * 80)

    segments = []

    with open(
        SEGMENTS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            segments.append(
                json.loads(line)
            )

    print()
    print(
        f"Segments loaded: {len(segments)}"
    )

    # ========================================================
    # BASIC DISTRIBUTIONS
    # ========================================================

    print()
    print("=" * 80)
    print("DOMINANT WORK AREA")
    print("=" * 80)

    areas = Counter(
        s.get(
            "dominant_work_area",
            "UNKNOWN"
        )
        for s in segments
    )

    for area, count in areas.most_common():

        print(
            f"{area:20s} {count:4d}"
        )

    # ========================================================
    # DURATION BUCKETS
    # ========================================================

    print()
    print("=" * 80)
    print("DURATION DISTRIBUTION")
    print("=" * 80)

    buckets = {
        "<10s": 0,
        "10-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        "120-300s": 0,
        ">300s": 0
    }

    for segment in segments:

        duration = segment.get(
            "duration_seconds",
            0
        )

        if duration < 10:
            buckets["<10s"] += 1

        elif duration < 30:
            buckets["10-30s"] += 1

        elif duration < 60:
            buckets["30-60s"] += 1

        elif duration < 120:
            buckets["60-120s"] += 1

        elif duration < 300:
            buckets["120-300s"] += 1

        else:
            buckets[">300s"] += 1

    for bucket, count in buckets.items():

        print(
            f"{bucket:15s} {count:4d}"
        )

    # ========================================================
    # BUSINESS SYSTEM / APPLICATION COMBINATIONS
    # ========================================================

    print()
    print("=" * 80)
    print("COMMON APPLICATION COMBINATIONS")
    print("=" * 80)

    combinations = Counter()

    for segment in segments:

        apps = [
            x["name"]
            for x in segment.get(
                "applications",
                []
            )
        ]

        # Keep top applications only
        apps = apps[:5]

        key = " -> ".join(apps)

        combinations[key] += 1

    for combo, count in combinations.most_common(30):

        print(
            f"{count:4d}  {combo}"
        )

    # ========================================================
    # WINDOW TITLE PATTERNS
    # ========================================================

    print()
    print("=" * 80)
    print("COMMON WINDOW TITLE PATTERNS")
    print("=" * 80)

    titles = Counter()

    for segment in segments:

        for item in segment.get(
            "window_titles",
            []
        ):

            titles[
                item["title"]
            ] += item["events"]

    for title, count in titles.most_common(40):

        print(
            f"{count:5d}  {title}"
        )

    # ========================================================
    # SAMPLE SEGMENTS
    # ========================================================

    print()
    print("=" * 80)
    print("SAMPLE SEGMENTS")
    print("=" * 80)

    # Show representative examples:
    # shortest, longest, and several normal-sized segments

    sorted_segments = sorted(
        segments,
        key=lambda s: s.get(
            "duration_seconds",
            0
        )
    )

    selected = []

    # Short
    selected.extend(
        sorted_segments[:5]
    )

    # Middle
    middle = len(
        sorted_segments
    ) // 2

    selected.extend(
        sorted_segments[
            max(0, middle - 2):
            middle + 3
        ]
    )

    # Long
    selected.extend(
        sorted_segments[-5:]
    )

    # Remove duplicates
    seen = set()

    unique_selected = []

    for segment in selected:

        segment_id = segment.get(
            "segment_id"
        )

        if segment_id in seen:
            continue

        seen.add(
            segment_id
        )

        unique_selected.append(
            segment
        )

    for segment in unique_selected:

        print()
        print("-" * 80)

        print(
            "SEGMENT:",
            segment.get(
                "segment_id"
            )
        )

        print(
            "Session:",
            segment.get(
                "session_id"
            )
        )

        print(
            "Chunk:",
            segment.get(
                "chunk_id"
            )
        )

        print(
            "Duration:",
            f"{segment.get('duration_seconds', 0):.1f}s"
        )

        print(
            "Events:",
            segment.get(
                "event_count"
            )
        )

        print(
            "Area:",
            segment.get(
                "dominant_work_area"
            )
        )

        print(
            "App:",
            segment.get(
                "dominant_app"
            )
        )

        print(
            "Applications:"
        )

        for app in segment.get(
            "applications",
            []
        )[:5]:

            print(
                f"  {app['name']}: "
                f"{app['events']}"
            )

        print(
            "Window titles:"
        )

        for title in segment.get(
            "window_titles",
            []
        )[:5]:

            print(
                f"  {title['title']}: "
                f"{title['events']}"
            )

        print(
            "Event types:"
        )

        for event_type in segment.get(
            "event_types",
            []
        )[:8]:

            print(
                f"  {event_type['event_type']}: "
                f"{event_type['count']}"
            )

        print(
            "Boundary evidence:"
        )

        evidence = segment.get(
            "boundary_evidence",
            {}
        )

        print(
            f"  score = "
            f"{evidence.get('score', 0)}"
        )

        for reason in evidence.get(
            "reasons",
            []
        ):

            print(
                f"  - {reason}"
            )

        print(
            "Text evidence:"
        )

        for text in segment.get(
            "text_evidence",
            []
        )[:5]:

            print(
                f"  {text[:200]}"
            )

    print()
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()