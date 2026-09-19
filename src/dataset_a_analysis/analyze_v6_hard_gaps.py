from pathlib import Path
import json
from collections import Counter


PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v6.jsonl"
)


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

    boundary_counts = Counter(
        s.get("boundary_before")
        for s in segments
    )

    print("=" * 80)
    print("V6 BOUNDARY DIAGNOSTIC")
    print("=" * 80)

    print(f"Total segments: {len(segments)}")

    print("\n--- Boundary types ---")
    for boundary, count in boundary_counts.most_common():
        print(f"{str(boundary):35} {count}")

    # Analyze hard-gap segments
    hard_gap_segments = [
        s for s in segments
        if s.get("boundary_before") == "hard_gap"
    ]

    print("\n--- Hard-gap segments ---")
    print(f"Count: {len(hard_gap_segments)}")

    if not hard_gap_segments:
        print("No hard-gap segments found.")
        return

    durations = [
        s["duration_seconds"]
        for s in hard_gap_segments
    ]

    event_counts = [
        s["event_count"]
        for s in hard_gap_segments
    ]

    print(f"Min duration    : {min(durations):.3f}s")
    print(f"Max duration    : {max(durations):.3f}s")
    print(f"Avg duration    : {sum(durations) / len(durations):.3f}s")

    print(f"Min events      : {min(event_counts)}")
    print(f"Max events      : {max(event_counts)}")
    print(f"Avg events      : {sum(event_counts) / len(event_counts):.2f}")

    print("\n--- Duration buckets ---")

    buckets = Counter()

    for d in durations:
        if d < 1:
            buckets["<1s"] += 1
        elif d < 2:
            buckets["1-2s"] += 1
        elif d < 5:
            buckets["2-5s"] += 1
        elif d < 10:
            buckets["5-10s"] += 1
        elif d < 20:
            buckets["10-20s"] += 1
        else:
            buckets[">=20s"] += 1

    for bucket in [
        "<1s",
        "1-2s",
        "2-5s",
        "5-10s",
        "10-20s",
        ">=20s",
    ]:
        print(f"{bucket:8} : {buckets[bucket]}")

    print("\n--- First event types ---")

    first_types = Counter(
        s.get("first_event_type")
        for s in hard_gap_segments
    )

    for event_type, count in first_types.most_common():
        print(f"{str(event_type):30} {count}")

    print("\n--- Last event types ---")

    last_types = Counter(
        s.get("last_event_type")
        for s in hard_gap_segments
    )

    for event_type, count in last_types.most_common():
        print(f"{str(event_type):30} {count}")

    print("\n--- 30 shortest hard-gap segments ---")

    shortest = sorted(
        hard_gap_segments,
        key=lambda s: s["duration_seconds"]
    )[:30]

    for i, s in enumerate(shortest, 1):
        print(
            f"{i:2}. "
            f"duration={s['duration_seconds']:7.3f}s "
            f"events={s['event_count']:3} "
            f"first={s.get('first_event_type')} "
            f"last={s.get('last_event_type')} "
            f"session={s.get('session_id')}"
        )

    print("\n" + "=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    main()