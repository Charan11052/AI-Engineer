import json
from pathlib import Path
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parents[2]

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


def main():
    print("=" * 70)
    print("DATASET A — INSPECT GT RECORD TYPES")
    print("=" * 70)

    records = []

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            records.append(json.loads(line))

    print(f"\nTotal records: {len(records):,}")

    print("\nRecords by timestamp completeness")
    print("-" * 70)

    both = 0
    missing_start = 0
    missing_end = 0
    missing_both = 0

    for record in records:
        start = record.get("start_ts")
        end = record.get("end_ts")

        if start and end:
            both += 1
        elif start and not end:
            missing_end += 1
        elif not start and end:
            missing_start += 1
        else:
            missing_both += 1

    print(f"Start + End present : {both:,}")
    print(f"Missing End         : {missing_end:,}")
    print(f"Missing Start       : {missing_start:,}")
    print(f"Missing Both        : {missing_both:,}")

    print("\nProcess codes")
    print("-" * 70)

    process_counts = Counter(
        record.get("process_code")
        for record in records
    )

    for process, count in process_counts.most_common():
        print(f"{str(process):20s} {count:6,}")

    print("\nExecution ID presence")
    print("-" * 70)

    with_execution_id = sum(
        1 for record in records
        if record.get("execution_id")
    )

    without_execution_id = len(records) - with_execution_id

    print(f"With execution_id    : {with_execution_id:,}")
    print(f"Without execution_id : {without_execution_id:,}")

    print("\nSample records missing end_ts")
    print("-" * 70)

    shown = 0

    for record in records:
        if record.get("start_ts") and not record.get("end_ts"):
            print(json.dumps(record, indent=2, ensure_ascii=False))

            shown += 1

            if shown >= 5:
                break

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()