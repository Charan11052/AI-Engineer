import json
import statistics
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SEGMENTS_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b_segments_v6.jsonl"
)

OUTPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b_automation_roi.json"
)


def load_segments():
    segments = []

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def analyze(segments):
    grouped = {}

    for segment in segments:
        task = segment.get("task")

        if not task:
            continue

        grouped.setdefault(task, []).append(
            segment["duration_seconds"]
        )

    results = []

    for task, durations in grouped.items():

        count = len(durations)
        total_seconds = sum(durations)
        average = statistics.mean(durations)
        median = statistics.median(durations)

        # Conservative assumption:
        # automation could remove 70% of the repetitive
        # execution time while keeping human review available.
        estimated_saved_seconds = total_seconds * 0.70

        results.append({
            "task": task,
            "executions": count,
            "total_seconds": round(total_seconds, 2),
            "total_minutes": round(total_seconds / 60, 2),
            "average_seconds": round(average, 2),
            "median_seconds": round(median, 2),
            "estimated_saved_seconds": round(
                estimated_saved_seconds, 2
            ),
            "estimated_saved_minutes": round(
                estimated_saved_seconds / 60, 2
            )
        })

    results.sort(
        key=lambda x: x["estimated_saved_seconds"],
        reverse=True
    )

    return results


def main():
    segments = load_segments()

    results = analyze(segments)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("DATASET B AUTOMATION ROI ANALYSIS")
    print("=" * 55)

    for rank, item in enumerate(results, start=1):
        print(
            f"{rank}. {item['task']:<25} "
            f"{item['executions']:>3} executions | "
            f"{item['total_minutes']:>7.2f} min observed | "
            f"{item['estimated_saved_minutes']:>7.2f} min "
            f"potential saving"
        )

    print()
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()