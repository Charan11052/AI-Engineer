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

    checkpoint_segments = [
        s for s in segments
        if s.get("boundary_before") == "checkpoint_transition_burst"
    ]

    print("=" * 80)
    print("V6 CHECKPOINT-TRANSITION DIAGNOSTIC")
    print("=" * 80)

    print(f"Total V6 segments                  : {len(segments)}")
    print(f"Checkpoint-transition boundaries   : {len(checkpoint_segments)}")

    if not checkpoint_segments:
        print("No checkpoint-transition segments found.")
        return

    durations = [
        s["duration_seconds"]
        for s in checkpoint_segments
    ]

    event_counts = [
        s["event_count"]
        for s in checkpoint_segments
    ]

    print("\n--- Duration ---")
    print(f"Min    : {min(durations):.3f}s")
    print(f"Median : {sorted(durations)[len(durations)//2]:.3f}s")
    print(f"Max    : {max(durations):.3f}s")
    print(f"Avg    : {sum(durations) / len(durations):.3f}s")

    print("\n--- Event count ---")
    print(f"Min    : {min(event_counts)}")
    print(f"Median : {sorted(event_counts)[len(event_counts)//2]}")
    print(f"Max    : {max(event_counts)}")
    print(f"Avg    : {sum(event_counts) / len(event_counts):.2f}")

    print("\n--- Duration buckets ---")

    buckets = Counter()

    for d in durations:
        if d < 5:
            buckets["<5s"] += 1
        elif d < 10:
            buckets["5-10s"] += 1
        elif d < 15:
            buckets["10-15s"] += 1
        elif d < 20:
            buckets["15-20s"] += 1
        elif d < 30:
            buckets["20-30s"] += 1
        elif d < 60:
            buckets["30-60s"] += 1
        else:
            buckets[">=60s"] += 1

    for bucket in [
        "<5s",
        "5-10s",
        "10-15s",
        "15-20s",
        "20-30s",
        "30-60s",
        ">=60s",
    ]:
        print(f"{bucket:8} : {buckets[bucket]}")

    print("\n--- First event types ---")

    first_types = Counter(
        s.get("first_event_type")
        for s in checkpoint_segments
    )

    for event_type, count in first_types.most_common():
        print(f"{str(event_type):30} {count}")

    print("\n--- Last event types ---")

    last_types = Counter(
        s.get("last_event_type")
        for s in checkpoint_segments
    )

    for event_type, count in last_types.most_common():
        print(f"{str(event_type):30} {count}")

    print("\n--- 40 shortest checkpoint-transition segments ---")

    shortest = sorted(
        checkpoint_segments,
        key=lambda s: s["duration_seconds"]
    )[:40]

    for i, s in enumerate(shortest, 1):
        print(
            f"{i:2}. "
            f"duration={s['duration_seconds']:7.3f}s "
            f"events={s['event_count']:3} "
            f"first={s.get('first_event_type'):25} "
            f"last={s.get('last_event_type'):25}"
        )

    print("\n--- 20 longest checkpoint-transition segments ---")

    longest = sorted(
        checkpoint_segments,
        key=lambda s: s["duration_seconds"],
        reverse=True
    )[:20]

    for i, s in enumerate(longest, 1):
        print(
            f"{i:2}. "
            f"duration={s['duration_seconds']:7.3f}s "
            f"events={s['event_count']:3} "
            f"first={s.get('first_event_type'):25} "
            f"last={s.get('last_event_type'):25}"
        )

    print("\n" + "=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    main()