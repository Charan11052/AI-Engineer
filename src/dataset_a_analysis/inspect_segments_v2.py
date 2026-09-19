import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v2.jsonl"


def load_segments():
    segments = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def main():

    segments = load_segments()

    print("=" * 70)
    print("DATASET B V2 SEGMENT INSPECTION")
    print("=" * 70)

    print(f"Total segments: {len(segments)}")

    # --------------------------------------------------------
    # Duration distribution
    # --------------------------------------------------------

    print("\nDURATION DISTRIBUTION")

    buckets = {
        "<5s": 0,
        "5-10s": 0,
        "10-20s": 0,
        "20-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        "120-180s": 0,
        ">180s": 0,
    }

    for s in segments:
        d = s["duration_seconds"]

        if d < 5:
            buckets["<5s"] += 1
        elif d < 10:
            buckets["5-10s"] += 1
        elif d < 20:
            buckets["10-20s"] += 1
        elif d < 30:
            buckets["20-30s"] += 1
        elif d < 60:
            buckets["30-60s"] += 1
        elif d < 120:
            buckets["60-120s"] += 1
        elif d < 180:
            buckets["120-180s"] += 1
        else:
            buckets[">180s"] += 1

    for bucket, count in buckets.items():
        print(f"  {bucket:10s} {count:4d}")

    # --------------------------------------------------------
    # Areas
    # --------------------------------------------------------

    print("\nDOMINANT AREAS")

    areas = Counter(
        s["dominant_area"]
        for s in segments
    )

    for area, count in areas.most_common():
        print(f"  {area:15s} {count:4d}")

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    print("\nDOMINANT TASKS")

    tasks = Counter(
        s["dominant_task"] or "NONE"
        for s in segments
    )

    for task, count in tasks.most_common():
        print(f"  {task:35s} {count:4d}")

    # --------------------------------------------------------
    # Very short segments
    # --------------------------------------------------------

    print("\nVERY SHORT SEGMENTS (<10s)")

    short_segments = [
        s for s in segments
        if s["duration_seconds"] < 10
    ]

    print(f"Count: {len(short_segments)}")

    for s in short_segments[:30]:

        print("\n" + "-" * 70)

        print(
            f"ID: {s['segment_id']}"
        )

        print(
            f"Duration: {s['duration_seconds']}s | "
            f"Events: {s['event_count']}"
        )

        print(
            f"Area: {s['dominant_area']} | "
            f"Task: {s['dominant_task']}"
        )

        print(
            f"Confidence: {s['confidence']}"
        )

        print(
            f"Boundary evidence: "
            f"{s['boundary_evidence']}"
        )

        print(
            "Apps:",
            list(s["apps"].keys())
        )

        print(
            "Titles:",
            list(s["window_titles"].keys())[:8]
        )

        print(
            "Text evidence:"
        )

        for text in s["text_evidence"][:5]:
            print(
                f"  {text[:250]}"
            )

    # --------------------------------------------------------
    # Long mixed segments
    # --------------------------------------------------------

    print("\nLONG SEGMENTS (>150s)")

    long_segments = [
        s for s in segments
        if s["duration_seconds"] > 150
    ]

    print(f"Count: {len(long_segments)}")

    for s in long_segments:

        print("\n" + "-" * 70)

        print(
            f"ID: {s['segment_id']}"
        )

        print(
            f"Duration: {s['duration_seconds']}s | "
            f"Events: {s['event_count']}"
        )

        print(
            f"Area: {s['dominant_area']} | "
            f"Task: {s['dominant_task']}"
        )

        print(
            "Areas:",
            s["areas"]
        )

        print(
            "Tasks:",
            s["task_signatures"]
        )

        print(
            "Documents:",
            s["documents"]
        )

        print(
            "Top titles:"
        )

        for title, count in list(
            s["window_titles"].items()
        )[:10]:
            print(
                f"  {count:4d}  {title[:180]}"
            )

        print(
            "Text evidence:"
        )

        for text in s["text_evidence"][:8]:
            print(
                f"  {text[:250]}"
            )

    # --------------------------------------------------------
    # Application patterns
    # --------------------------------------------------------

    print("\nCOMMON APPLICATION PATTERNS")

    patterns = Counter()

    for s in segments:

        apps = list(s["apps"].keys())

        # preserve first-seen order but remove duplicates
        unique = []

        for app in apps:
            if app not in unique:
                unique.append(app)

        pattern = " -> ".join(unique)

        patterns[pattern] += 1

    for pattern, count in patterns.most_common(25):

        print(
            f"  {count:4d}  {pattern}"
        )

    # --------------------------------------------------------
    # Boundary reasons
    # --------------------------------------------------------

    print("\nBOUNDARY EVIDENCE")

    reasons = Counter()

    for s in segments:
        for reason in s.get(
            "boundary_evidence",
            []
        ):
            reasons[reason] += 1

    for reason, count in reasons.most_common():

        print(
            f"  {count:4d}  {reason}"
        )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()