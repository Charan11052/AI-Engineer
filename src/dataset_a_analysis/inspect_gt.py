import json
from pathlib import Path
from pprint import pprint


PROJECT_DIR = Path(r"D:\CHARAN RONGALI\AI Engineer")
DATASET_DIR = PROJECT_DIR / "dataset_a"


def main():

    # Find the first gt.jsonl anywhere inside Dataset A
    gt_files = list(DATASET_DIR.rglob("gt.jsonl"))

    print("=" * 70)
    print("GROUND TRUTH STRUCTURE INSPECTION")
    print("=" * 70)

    print(f"\nGT files found: {len(gt_files)}")

    if not gt_files:
        print("\nERROR: No gt.jsonl files found.")
        return

    gt_file = gt_files[0]

    print(f"\nInspecting:")
    print(gt_file)

    print("\n" + "=" * 70)
    print("FIRST 10 GT RECORDS")
    print("=" * 70)

    with gt_file.open("r", encoding="utf-8") as f:

        for i, line in enumerate(f):

            if i >= 10:
                break

            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

                print(f"\n--- RECORD {i + 1} ---")
                pprint(record, sort_dicts=False)

            except json.JSONDecodeError as e:

                print(
                    f"ERROR parsing line {i + 1}: {e}"
                )

    print("\n" + "=" * 70)
    print("KEYS FOUND IN FIRST RECORD")
    print("=" * 70)

    with gt_file.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            record = json.loads(line)

            print(
                "\nTop-level keys:"
            )

            for key in record.keys():
                print(
                    f"  {key}: "
                    f"{type(record[key]).__name__}"
                )

            break


if __name__ == "__main__":
    main()