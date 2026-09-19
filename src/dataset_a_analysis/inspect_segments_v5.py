import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "outputs" / "dataset_b_segments_v5.jsonl"


def main():

    segments = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            segments.append(json.loads(line))

    print("=" * 80)
    print("DATASET B V5 SEGMENT INSPECTION")
    print("=" * 80)

    print(f"Total segments: {len(segments)}")

    # --------------------------------------------------------
    # SHORTEST SEGMENTS
    # --------------------------------------------------------

    shortest = sorted(
        segments,
        key=lambda x: x["duration_seconds"]
    )[:30]

    print()
    print("=" * 80)
    print("30 SHORTEST SEGMENTS")
    print("=" * 80)

    for i, segment in enumerate(shortest, 1):

        print()
        print("-" * 80)

        print(
            f"{i}. {segment['segment_id']}"
        )

        print(
            f"Task: {segment['task']}"
        )

        print(
            f"Area: {segment['business_area']}"
        )

        print(
            f"Duration: {segment['duration_seconds']} sec"
        )

        print(
            f"Events: {segment['event_count']}"
        )

        print(
            f"Apps: {segment['applications']}"
        )

        print(
            f"Supporting tasks: "
            f"{segment['supporting_tasks']}"
        )

        print(
            f"Completion evidence: "
            f"{segment['completion_evidence']}"
        )

    # --------------------------------------------------------
    # LONGEST SEGMENTS
    # --------------------------------------------------------

    longest = sorted(
        segments,
        key=lambda x: x["duration_seconds"],
        reverse=True
    )[:15]

    print()
    print("=" * 80)
    print("15 LONGEST SEGMENTS")
    print("=" * 80)

    for i, segment in enumerate(longest, 1):

        print()
        print("-" * 80)

        print(
            f"{i}. {segment['segment_id']}"
        )

        print(
            f"Task: {segment['task']}"
        )

        print(
            f"Area: {segment['business_area']}"
        )

        print(
            f"Duration: {segment['duration_seconds']} sec"
        )

        print(
            f"Events: {segment['event_count']}"
        )

        print(
            f"Apps: {segment['applications']}"
        )

        print(
            f"Supporting tasks: "
            f"{segment['supporting_tasks']}"
        )

        print(
            f"Completion evidence: "
            f"{segment['completion_evidence']}"
        )

    # --------------------------------------------------------
    # TASK + DURATION
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("TASK DURATION SUMMARY")
    print("=" * 80)

    task_data = {}

    for segment in segments:

        task = segment["task"]

        task_data.setdefault(
            task,
            []
        ).append(
            segment["duration_seconds"]
        )

    for task, durations in sorted(
        task_data.items()
    ):

        durations_sorted = sorted(durations)

        avg = sum(durations) / len(durations)

        median = durations_sorted[
            len(durations_sorted) // 2
        ]

        short = sum(
            1 for d in durations
            if d < 10
        )

        print(
            f"{task:25s} "
            f"count={len(durations):3d} "
            f"avg={avg:6.2f}s "
            f"median={median:6.2f}s "
            f"<10s={short:3d}"
        )


if __name__ == "__main__":
    main()