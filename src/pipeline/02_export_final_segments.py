import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b"
    / "dataset_b_segments_v8.jsonl"
)

OUTPUT_FILE = BASE_DIR / "segments.jsonl"


def to_iso_utc(timestamp_ms):
    dt = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc
    )

    return dt.isoformat().replace("+00:00", "Z")


def main():
    count = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as src, \
         open(OUTPUT_FILE, "w", encoding="utf-8") as dst:

        for line in src:
            line = line.strip()

            if not line:
                continue

            segment = json.loads(line)

            output = {
                "session_id": segment["session"],
                "start": to_iso_utc(
                    segment["start_timestamp_ms"]
                ),
                "end": to_iso_utc(
                    segment["end_timestamp_ms"]
                ),
                "label": segment["task"]
            }

            dst.write(
                json.dumps(
                    output,
                    ensure_ascii=False
                )
                + "\n"
            )

            count += 1

    print("FINAL DATASET B SUBMISSION")
    print("=" * 55)
    print(f"Segments written : {count}")
    print(f"Output           : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()