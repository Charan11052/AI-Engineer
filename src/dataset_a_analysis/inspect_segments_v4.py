import json
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "dataset_b_segments_v4.jsonl"


def load_segments():
    segments = []

    with INPUT.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def print_segment(seg):

    print("=" * 80)

    print(
        f"ID: {seg['id']}"
    )

    print(
        f"Duration: {seg['duration_seconds']}s | "
        f"Events: {seg['event_count']}"
    )

    print(
        f"Area: {seg['area']} | "
        f"Task: {seg['task']} | "
        f"Confidence: {seg['confidence']}"
    )

    print(
        f"Completion: "
        f"{seg.get('completion_evidence', '')}"
    )

    print()

    print("Apps:")

    for k, v in seg.get("apps", {}).items():
        print(f"  {k}: {v}")

    print()

    print("Documents:")

    for k, v in seg.get("documents", {}).items():
        print(f"  {k}: {v}")

    print()

    print("Task evidence:")

    for k, v in seg.get(
        "explicit_task_evidence", {}
    ).items():

        print(f"  {k}: {v}")


def main():

    segments = load_segments()

    print("=" * 80)
    print("DATASET B - V4 SEGMENT INSPECTION")
    print("=" * 80)

    print(f"Total segments: {len(segments)}")

    # --------------------------------------------------------
    # Duration buckets
    # --------------------------------------------------------

    buckets = Counter()

    for s in segments:

        d = s["duration_seconds"]

        if d < 1:
            buckets["<1s"] += 1

        elif d < 5:
            buckets["1-5s"] += 1

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

    print()
    print("DURATION DISTRIBUTION")

    for k, v in buckets.items():
        print(f"  {k}: {v}")

    # --------------------------------------------------------
    # Task distribution
    # --------------------------------------------------------

    tasks = Counter(
        s["task"]
        for s in segments
    )

    print()
    print("TASK DISTRIBUTION")

    for task, count in tasks.most_common():

        print(
            f"  {task}: {count}"
        )

    # --------------------------------------------------------
    # Very short segments
    # --------------------------------------------------------

    short_segments = [
        s for s in segments
        if s["duration_seconds"] < 5
    ]

    print()
    print("=" * 80)
    print(
        f"VERY SHORT SEGMENTS "
        f"(<5s): {len(short_segments)}"
    )
    print("=" * 80)

    for s in short_segments[:20]:
        print_segment(s)

    # --------------------------------------------------------
    # Finance expense sample
    # --------------------------------------------------------

    finance_expense = [
        s for s in segments
        if s["task"] == "FINANCE_EXPENSE"
    ]

    print()
    print("=" * 80)
    print(
        f"FINANCE EXPENSE SAMPLE "
        f"(showing up to 10 of {len(finance_expense)})"
    )
    print("=" * 80)

    for s in finance_expense[:10]:
        print_segment(s)

    # --------------------------------------------------------
    # HR onboarding sample
    # --------------------------------------------------------

    onboarding = [
        s for s in segments
        if s["task"] == "HR_ONBOARDING"
    ]

    print()
    print("=" * 80)
    print(
        f"HR ONBOARDING SAMPLE "
        f"(showing up to 10 of {len(onboarding)})"
    )
    print("=" * 80)

    for s in onboarding[:10]:
        print_segment(s)

    # --------------------------------------------------------
    # Long segments
    # --------------------------------------------------------

    long_segments = sorted(
        segments,
        key=lambda s: s["duration_seconds"],
        reverse=True
    )

    print()
    print("=" * 80)
    print("LONGEST SEGMENTS")
    print("=" * 80)

    for s in long_segments[:10]:
        print_segment(s)


if __name__ == "__main__":
    main()