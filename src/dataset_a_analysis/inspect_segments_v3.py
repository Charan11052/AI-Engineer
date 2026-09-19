import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v3.jsonl"


def load_segments():
    segments = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def print_segment(s):

    print("\n" + "-" * 75)

    print("ID:", s["segment_id"])

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
        f"Completions: "
        f"{s.get('completion_evidence_count', 0)}"
    )

    print(
        "Areas:",
        s.get("areas", {})
    )

    print(
        "Tasks:",
        s.get("task_signatures", {})
    )

    print(
        "Documents:",
        s.get("documents", {})
    )

    print(
        "Boundary:",
        s.get("boundary_evidence", [])
    )

    print("Top titles:")

    for title, count in list(
        s.get("window_titles", {}).items()
    )[:10]:

        print(
            f"  {count:4d}  {title[:180]}"
        )

    print("Text evidence:")

    for text in s.get("text_evidence", [])[:8]:

        print(
            f"  {text[:300]}"
        )


def main():

    segments = load_segments()

    print("=" * 75)
    print("DATASET B V3 SEGMENT INSPECTION")
    print("=" * 75)

    print(
        f"Total segments: {len(segments)}"
    )

    # --------------------------------------------------------
    # Duration distribution
    # --------------------------------------------------------

    print("\nDURATION DISTRIBUTION")

    buckets = {
        "<5s": 0,
        "5-10s": 0,
        "10-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        "120-180s": 0,
        "180-300s": 0,
        ">300s": 0,
    }

    for s in segments:

        d = s["duration_seconds"]

        if d < 5:
            buckets["<5s"] += 1

        elif d < 10:
            buckets["5-10s"] += 1

        elif d < 30:
            buckets["10-30s"] += 1

        elif d < 60:
            buckets["30-60s"] += 1

        elif d < 120:
            buckets["60-120s"] += 1

        elif d < 180:
            buckets["120-180s"] += 1

        elif d < 300:
            buckets["180-300s"] += 1

        else:
            buckets[">300s"] += 1

    for bucket, count in buckets.items():

        print(
            f"  {bucket:10s} {count:4d}"
        )

    # --------------------------------------------------------
    # Task distribution
    # --------------------------------------------------------

    print("\nTASK DISTRIBUTION")

    tasks = Counter(
        s["dominant_task"] or "NONE"
        for s in segments
    )

    for task, count in tasks.most_common():

        print(
            f"  {task:35s} {count:4d}"
        )

    # --------------------------------------------------------
    # Very short segments
    # --------------------------------------------------------

    short = [
        s for s in segments
        if s["duration_seconds"] < 10
    ]

    print(
        f"\nSHORT SEGMENTS (<10s): {len(short)}"
    )

    for s in short:

        print_segment(s)

    # --------------------------------------------------------
    # Very long segments
    # --------------------------------------------------------

    long = [
        s for s in segments
        if s["duration_seconds"] > 150
    ]

    print(
        f"\nLONG SEGMENTS (>150s): {len(long)}"
    )

    for s in long:

        print_segment(s)

    # --------------------------------------------------------
    # Most mixed segments
    # --------------------------------------------------------

    mixed = sorted(
        segments,
        key=lambda s: (
            len(s.get("task_signatures", {})),
            len(s.get("areas", {})),
            s["duration_seconds"]
        ),
        reverse=True
    )

    print(
        "\nMOST MIXED SEGMENTS"
    )

    for s in mixed[:15]:

        print("\n" + "-" * 75)

        print(
            s["segment_id"]
        )

        print(
            f"Duration: "
            f"{s['duration_seconds']}s | "
            f"Events: {s['event_count']}"
        )

        print(
            "Dominant:",
            s["dominant_area"],
            s["dominant_task"]
        )

        print(
            "Areas:",
            s.get("areas", {})
        )

        print(
            "Tasks:",
            s.get("task_signatures", {})
        )

        print(
            "Documents:",
            s.get("documents", {})
        )

    print("\n" + "=" * 75)


if __name__ == "__main__":
    main()