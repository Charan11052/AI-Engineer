import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v6.jsonl"
)


def main():

    segments = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            segments.append(json.loads(line))

    print("=" * 80)
    print("DATASET A V6 SEGMENT INSPECTION")
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

        print(f"{i}. {segment['segment_id']}")
        print(f"Duration: {segment['duration_seconds']} sec")
        print(f"Events: {segment['event_count']}")
        print(f"Apps: {segment['apps']}")
        print(f"First event: {segment['first_event_type']}")
        print(f"Last event: {segment['last_event_type']}")
        print(f"Boundary: {segment['boundary_before']}")

    # --------------------------------------------------------
    # LONGEST SEGMENTS
    # --------------------------------------------------------

    longest = sorted(
        segments,
        key=lambda x: x["duration_seconds"],
        reverse=True
    )[:20]

    print()
    print("=" * 80)
    print("20 LONGEST SEGMENTS")
    print("=" * 80)

    for i, segment in enumerate(longest, 1):

        print()
        print("-" * 80)

        print(f"{i}. {segment['segment_id']}")
        print(f"Duration: {segment['duration_seconds']} sec")
        print(f"Events: {segment['event_count']}")
        print(f"Apps: {segment['apps']}")
        print(f"First event: {segment['first_event_type']}")
        print(f"Last event: {segment['last_event_type']}")
        print(f"Boundary: {segment['boundary_before']}")

    # --------------------------------------------------------
    # BOUNDARY SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("BOUNDARY SUMMARY")
    print("=" * 80)

    reasons = {}

    for segment in segments:

        reason = segment["boundary_before"]

        reasons[reason] = (
            reasons.get(reason, 0) + 1
        )

    for reason, count in sorted(
        reasons.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{reason:40s} {count:6d}"
        )

    # --------------------------------------------------------
    # START / END EVENT SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("PREDICTED FIRST EVENT TYPES")
    print("=" * 80)

    first_events = {}

    for segment in segments:

        event_type = segment["first_event_type"]

        first_events[event_type] = (
            first_events.get(event_type, 0) + 1
        )

    for event_type, count in sorted(
        first_events.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{event_type:30s} {count:6d}"
        )

    print()
    print("=" * 80)
    print("PREDICTED LAST EVENT TYPES")
    print("=" * 80)

    last_events = {}

    for segment in segments:

        event_type = segment["last_event_type"]

        last_events[event_type] = (
            last_events.get(event_type, 0) + 1
        )

    for event_type, count in sorted(
        last_events.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{event_type:30s} {count:6d}"
        )


if __name__ == "__main__":
    main()