import json
from pathlib import Path
from collections import Counter


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_DIR / "data" / "dataset_a"


# ============================================================
# JSONL READER
# ============================================================

def read_jsonl(path):
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(
                    f"WARNING: Invalid JSON in {path} "
                    f"line {line_number}: {e}"
                )

    return records


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET A - GROUND TRUTH INSPECTION")
    print("=" * 70)

    if not DATASET_DIR.exists():
        print("\nERROR:")
        print("Dataset directory does not exist:")
        print(DATASET_DIR.resolve())
        return

    gt_files = sorted(DATASET_DIR.rglob("gt.jsonl"))

    print(f"\nDataset path : {DATASET_DIR.resolve()}")
    print(f"GT files found: {len(gt_files)}")

    if not gt_files:
        print("\nERROR: No gt.jsonl files found.")
        return

    event_counts = Counter()
    process_counts = Counter()
    variant_counts = Counter()

    total_records = 0
    total_executions = 0

    # --------------------------------------------------------
    # INSPECT GT FILES
    # --------------------------------------------------------

    for index, gt_file in enumerate(gt_files, start=1):

        records = read_jsonl(gt_file)

        print(
            f"[{index:02d}/{len(gt_files):02d}] "
            f"{gt_file.parent.name}"
        )

        print(
            f"       records: {len(records)}"
        )

        total_records += len(records)

        for record in records:

            event_name = record.get("event")

            if event_name:
                event_counts[event_name] += 1

            if event_name == "process_started":

                total_executions += 1

                process = record.get("process_code")

                if process:
                    process_counts[process] += 1

                variant = record.get("process_variant")

                variant_key = (
                    "None"
                    if variant is None
                    else str(variant)
                )

                variant_counts[variant_key] += 1

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 70)
    print("GROUND TRUTH SUMMARY")
    print("=" * 70)

    print(f"GT files              : {len(gt_files)}")
    print(f"Total GT records      : {total_records:,}")
    print(f"Process executions    : {total_executions:,}")
    print(f"Unique process types  : {len(process_counts)}")

    print("\n" + "=" * 70)
    print("GT EVENT TYPES")
    print("=" * 70)

    for name, count in event_counts.most_common():
        print(f"{name:30} {count:10,}")

    print("\n" + "=" * 70)
    print("PROCESS DISTRIBUTION")
    print("=" * 70)

    for process, count in process_counts.most_common():
        percentage = (
            count / total_executions * 100
            if total_executions
            else 0
        )

        print(
            f"Process {process:15} "
            f"{count:8,} "
            f"{percentage:7.2f}%"
        )

    print("\n" + "=" * 70)
    print("VARIANT DISTRIBUTION")
    print("=" * 70)

    for variant, count in variant_counts.most_common():
        percentage = (
            count / total_executions * 100
            if total_executions
            else 0
        )

        print(
            f"{variant:20} "
            f"{count:8,} "
            f"{percentage:7.2f}%"
        )

    # ========================================================
    # SAMPLE
    # ========================================================

    print("\n" + "=" * 70)
    print("SAMPLE GT RECORDS")
    print("=" * 70)

    sample_records = read_jsonl(gt_files[0])

    for record in sample_records[:10]:
        print(json.dumps(
            record,
            ensure_ascii=False,
            indent=2
        ))

    print("\nGround truth inspection completed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()