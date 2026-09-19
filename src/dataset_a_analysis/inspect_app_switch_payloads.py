from pathlib import Path
import json


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"

TARGET_SESSION = "ses_20260701-152030-CHAITANYA0BCF"


def main():
    count = 0

    for path in DATASET_A.rglob("events.jsonl"):

        with path.open("r", encoding="utf-8") as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                if event.get("session_id") != TARGET_SESSION:
                    continue

                if event.get("event_type") != "app_switch":
                    continue

                count += 1

                print()
                print("=" * 100)
                print(f"APP_SWITCH #{count}")
                print("=" * 100)

                print(
                    json.dumps(
                        event,
                        indent=2,
                        ensure_ascii=False
                    )
                )

                if count >= 10:
                    print()
                    print("=" * 100)
                    print("Displayed first 10 app_switch events.")
                    print("=" * 100)
                    return


if __name__ == "__main__":
    main()