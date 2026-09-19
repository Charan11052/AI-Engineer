import json
import statistics
from collections import defaultdict
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
    / "dataset_b_people_variants.json"
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
    people = defaultdict(list)
    task_variants = defaultdict(lambda: defaultdict(int))

    for segment in segments:
        session = segment.get("session", "unknown")
        task = segment.get("task", "UNKNOWN")
        supporting = tuple(
            sorted(segment.get("supporting_tasks", []))
        )

        people[session].append(segment)

        variant_key = (
            tuple(segment.get("applications", [])),
            supporting
        )

        task_variants[task][variant_key] += 1

    people_summary = []

    for session, items in people.items():
        tasks = defaultdict(int)

        for item in items:
            tasks[item.get("task", "UNKNOWN")] += 1

        people_summary.append({
            "session": session,
            "executions": len(items),
            "tasks": dict(tasks)
        })

    variant_summary = {}

    for task, variants in task_variants.items():
        variant_summary[task] = {
            "distinct_handling_patterns": len(variants),
            "patterns": [
                {
                    "applications": list(key[0]),
                    "supporting_tasks": list(key[1]),
                    "executions": count
                }
                for key, count in variants.items()
            ]
        }

    result = {
        "unique_sessions": len(people),
        "session_summary": people_summary,
        "task_variants": variant_summary
    }

    return result


def main():
    segments = load_segments()
    result = analyze(segments)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("DATASET B PEOPLE AND VARIANT ANALYSIS")
    print("=" * 60)

    print(
        f"Distinct session/operator identifiers : "
        f"{result['unique_sessions']}"
    )

    print()

    print("Executions by session:")
    for item in result["session_summary"]:
        print(
            f"{item['session']}: "
            f"{item['executions']} executions"
        )

    print()
    print("Handling patterns by task:")

    for task, info in result["task_variants"].items():
        print(
            f"{task:<25} "
            f"{info['distinct_handling_patterns']} "
            f"distinct patterns"
        )

    print()
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()